"""
aws_setup.py — One-shot AWS infrastructure provisioner.

Creates:
  - SQS queue:          EmergencyTriageQueue
  - DynamoDB table:     SeattleIngestSeen  (dedup store)
  - IAM role:           EmergencyDashboardLambdaRole
  - Lambda function:    EmergencyTriageLambda  (SQS-triggered)
  - Lambda function:    SeattleIngestLambda    (EventBridge-triggered)
  - EventBridge rule:   SeattleIngest5Min
  - Writes SQS_QUEUE_URL back to ../.env

Run:
  python aws_setup.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv()

REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "EmergencyIncidents")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ACCOUNT_ID = None  # resolved below

SQS_QUEUE_NAME = "EmergencyTriageQueue"
SEEN_TABLE_NAME = "SeattleIngestSeen"
ROLE_NAME = "EmergencyDashboardLambdaRole"
TRIAGE_FUNCTION = "EmergencyTriageLambda"
INGEST_FUNCTION = "SeattleIngestLambda"
EB_RULE_NAME = "SeattleIngest5Min"

iam = boto3.client("iam", region_name=REGION)
sqs = boto3.client("sqs", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)
events = boto3.client("events", region_name=REGION)
ddb = boto3.client("dynamodb", region_name=REGION)
sts = boto3.client("sts", region_name=REGION)


def step(msg):
    print(f"\n{'='*60}\n{msg}\n{'='*60}")


def resolve_account_id():
    global ACCOUNT_ID
    ACCOUNT_ID = sts.get_caller_identity()["Account"]
    print(f"AWS Account: {ACCOUNT_ID}")


# ── SQS ───────────────────────────────────────────────────────────────────────

def create_sqs_queue() -> str:
    step("Creating SQS queue")
    try:
        resp = sqs.create_queue(
            QueueName=SQS_QUEUE_NAME,
            Attributes={
                "VisibilityTimeout": "120",        # 2 min — enough for Claude call
                "MessageRetentionPeriod": "86400", # 1 day
                "ReceiveMessageWaitTimeSeconds": "20",
            },
        )
        url = resp["QueueUrl"]
        print(f"Queue URL: {url}")
        return url
    except sqs.exceptions.QueueAlreadyExists:
        url = sqs.get_queue_url(QueueName=SQS_QUEUE_NAME)["QueueUrl"]
        print(f"Queue already exists: {url}")
        return url


def get_queue_arn(queue_url: str) -> str:
    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )
    return attrs["Attributes"]["QueueArn"]


# ── DynamoDB dedup table ───────────────────────────────────────────────────────

def create_seen_table():
    step("Creating SeattleIngestSeen DynamoDB table")
    try:
        ddb.create_table(
            TableName=SEEN_TABLE_NAME,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "incident_number", "AttributeType": "S"}
            ],
            KeySchema=[
                {"AttributeName": "incident_number", "KeyType": "HASH"}
            ],
        )
        ddb.get_waiter("table_exists").wait(TableName=SEEN_TABLE_NAME)
        # Enable TTL
        ddb.update_time_to_live(
            TableName=SEEN_TABLE_NAME,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
        )
        print(f"Created {SEEN_TABLE_NAME} with TTL enabled.")
    except ddb.exceptions.ResourceInUseException:
        print(f"{SEEN_TABLE_NAME} already exists.")


# ── IAM ───────────────────────────────────────────────────────────────────────

TRUST_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
})

INLINE_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:UpdateItem",
                "dynamodb:Scan",
            ],
            "Resource": [
                f"arn:aws:dynamodb:{REGION}:*:table/{TABLE_NAME}",
                f"arn:aws:dynamodb:{REGION}:*:table/{SEEN_TABLE_NAME}",
            ],
        },
        {
            "Effect": "Allow",
            "Action": [
                "sqs:SendMessage",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:GetQueueAttributes",
            ],
            "Resource": f"arn:aws:sqs:{REGION}:*:{SQS_QUEUE_NAME}",
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            "Resource": "arn:aws:logs:*:*:*",
        },
    ],
})


def create_iam_role() -> str:
    step("Creating IAM role")
    try:
        resp = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=TRUST_POLICY,
            Description="Emergency Dashboard Lambda execution role",
        )
        role_arn = resp["Role"]["Arn"]
        iam.put_role_policy(
            RoleName=ROLE_NAME,
            PolicyName="EmergencyDashboardPolicy",
            PolicyDocument=INLINE_POLICY,
        )
        print(f"Created role: {role_arn}")
        print("Waiting 10s for IAM propagation...")
        time.sleep(10)
        return role_arn
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
        print(f"Role already exists: {role_arn}")
        return role_arn


# ── Lambda packaging ──────────────────────────────────────────────────────────

def package_lambda(handler_file: str, extra_deps: list[str] | None = None) -> bytes:
    """Zip a Lambda handler + its pip dependencies into bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        pkg_dir = Path(tmp) / "pkg"
        pkg_dir.mkdir()

        if extra_deps:
            print(f"  Installing deps: {extra_deps} (linux/x86_64 binaries for Lambda)...")
            subprocess.check_call(
                [
                    sys.executable, "-m", "pip", "install", "-q",
                    "-t", str(pkg_dir),
                    "--platform", "manylinux2014_x86_64",
                    "--implementation", "cp",
                    "--python-version", "3.12",
                    "--only-binary=:all:",
                ] + extra_deps
            )

        shutil.copy(handler_file, pkg_dir / Path(handler_file).name)

        zip_path = Path(tmp) / "lambda.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in pkg_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(pkg_dir))

        return zip_path.read_bytes()


# ── Lambda deployment ─────────────────────────────────────────────────────────

def deploy_lambda(name: str, handler: str, zip_bytes: bytes, role_arn: str, env_vars: dict):
    step(f"Deploying Lambda: {name}")
    try:
        lam.create_function(
            FunctionName=name,
            Runtime="python3.12",
            Role=role_arn,
            Handler=handler,
            Code={"ZipFile": zip_bytes},
            Timeout=120,
            MemorySize=256,
            Environment={"Variables": env_vars},
        )
        lam.get_waiter("function_active").wait(FunctionName=name)
        print(f"Created {name}")
    except lam.exceptions.ResourceConflictException:
        lam.update_function_code(FunctionName=name, ZipFile=zip_bytes)
        lam.get_waiter("function_updated").wait(FunctionName=name)
        lam.update_function_configuration(
            FunctionName=name,
            Environment={"Variables": env_vars},
        )
        lam.get_waiter("function_updated").wait(FunctionName=name)
        print(f"Updated {name}")


# ── SQS trigger for triage Lambda ────────────────────────────────────────────

def add_sqs_trigger(queue_arn: str):
    step("Adding SQS trigger to triage Lambda")
    try:
        lam.create_event_source_mapping(
            EventSourceArn=queue_arn,
            FunctionName=TRIAGE_FUNCTION,
            BatchSize=5,
            MaximumBatchingWindowInSeconds=10,
        )
        print("SQS trigger added.")
    except lam.exceptions.ResourceConflictException:
        print("SQS trigger already exists.")


# ── EventBridge rule ──────────────────────────────────────────────────────────

def create_eventbridge_rule(ingest_function_arn: str):
    step("Creating EventBridge rule (every 5 minutes)")
    rule_arn = events.put_rule(
        Name=EB_RULE_NAME,
        ScheduleExpression="rate(5 minutes)",
        State="ENABLED",
        Description="Trigger Seattle 911 ingest Lambda every 5 minutes",
    )["RuleArn"]

    try:
        lam.add_permission(
            FunctionName=INGEST_FUNCTION,
            StatementId="EventBridgeInvoke",
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=rule_arn,
        )
    except lam.exceptions.ResourceConflictException:
        pass

    events.put_targets(
        Rule=EB_RULE_NAME,
        Targets=[{"Id": "SeattleIngestTarget", "Arn": ingest_function_arn}],
    )
    print(f"EventBridge rule created: {EB_RULE_NAME} → {INGEST_FUNCTION}")


# ── Write SQS_QUEUE_URL back to .env ─────────────────────────────────────────

def update_env(queue_url: str):
    env_path = Path(__file__).parent.parent / ".env"
    content = env_path.read_text()
    if "SQS_QUEUE_URL" in content:
        lines = [
            f"SQS_QUEUE_URL={queue_url}" if l.startswith("SQS_QUEUE_URL=") else l
            for l in content.splitlines()
        ]
        env_path.write_text("\n".join(lines) + "\n")
    else:
        with env_path.open("a") as f:
            f.write(f"\nSQS_QUEUE_URL={queue_url}\n")
    print(f"Updated .env with SQS_QUEUE_URL")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    resolve_account_id()

    queue_url = create_sqs_queue()
    queue_arn = get_queue_arn(queue_url)

    create_seen_table()

    role_arn = create_iam_role()

    # Package + deploy triage Lambda (needs anthropic SDK)
    print("\nPackaging triage Lambda (installing anthropic SDK — may take ~30s)...")
    triage_zip = package_lambda("lambda_triage.py", extra_deps=["anthropic"])
    deploy_lambda(
        name=TRIAGE_FUNCTION,
        handler="lambda_triage.handler",
        zip_bytes=triage_zip,
        role_arn=role_arn,
        env_vars={
            "DYNAMODB_TABLE_NAME": TABLE_NAME,
            "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        },
    )
    add_sqs_trigger(queue_arn)

    # Package + deploy ingest Lambda (stdlib + boto3 only — no extra deps)
    print("\nPackaging ingest Lambda...")
    ingest_zip = package_lambda("lambda_ingest.py")
    deploy_lambda(
        name=INGEST_FUNCTION,
        handler="lambda_ingest.handler",
        zip_bytes=ingest_zip,
        role_arn=role_arn,
        env_vars={
            "DYNAMODB_TABLE_NAME": TABLE_NAME,
            "SEEN_TABLE_NAME": SEEN_TABLE_NAME,
            "SQS_QUEUE_URL": queue_url,
        },
    )

    ingest_arn = lam.get_function(FunctionName=INGEST_FUNCTION)["Configuration"]["FunctionArn"]
    create_eventbridge_rule(ingest_arn)

    update_env(queue_url)

    step("DONE")
    print(f"SQS Queue URL : {queue_url}")
    print(f"Triage Lambda : {TRIAGE_FUNCTION} (triggered by SQS)")
    print(f"Ingest Lambda : {INGEST_FUNCTION} (triggered by EventBridge every 5 min)")
    print(f"\nNext: restart the FastAPI server — POST /incident will now use SQS.")


if __name__ == "__main__":
    main()
