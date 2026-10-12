#!/usr/bin/env bash
# One-time setup that makes the factor-base archive permanent (README: "Keeping the
# archive forever"). Run it on your own machine, not in CI:
#
#   BUCKET=my-fb-archive ./setup_permanent_archive.sh
#
# Needs: the aws CLI, logged in as an account that may create buckets and IAM users;
# the GitHub CLI (gh), logged in as a repository admin; jq.
#
# It does four things, each skipped if already done:
#   1. creates an S3 bucket with Object Lock and a default COMPLIANCE retention
#      (no one, including the AWS root account, can delete a locked object version
#      before its retention ends -- this is irreversible, so it asks first);
#   2. creates an IAM user that may only put, get and list in that bucket (no delete)
#      and an access key for it;
#   3. stores IC_ARCHIVE_S3_URI, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and
#      AWS_DEFAULT_REGION as repository secrets;
#   4. adds a ruleset that blocks force pushes to, and deletion of, the default branch.
# Then it starts the fb-archive-offsite workflow once (if it is on the default branch).
set -euo pipefail

REPO="${REPO:-aburan28/cryptanalysis}"
BUCKET="${BUCKET:?set BUCKET to a new, globally unique S3 bucket name}"
REGION="${REGION:-us-east-1}"
PREFIX="${PREFIX:-cryptanalysis}"
RETENTION_YEARS="${RETENTION_YEARS:-100}"
IAM_USER="${IAM_USER:-fb-archive-uploader}"

for tool in aws gh jq; do
  command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 1; }
done
aws sts get-caller-identity >/dev/null || { echo "aws CLI is not logged in" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "gh is not logged in (gh auth login)" >&2; exit 1; }

echo "repository:  $REPO"
echo "bucket:      s3://$BUCKET/$PREFIX  ($REGION)"
echo "retention:   $RETENTION_YEARS years, COMPLIANCE mode (cannot be shortened or removed)"
echo "IAM user:    $IAM_USER (put/get/list only)"
read -r -p "Type the bucket name to confirm: " answer
[ "$answer" = "$BUCKET" ] || { echo "not confirmed; nothing done"; exit 1; }

# ---------------------------------------------------------------- 1. bucket
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "bucket exists; checking that Object Lock is on"
  aws s3api get-object-lock-configuration --bucket "$BUCKET" >/dev/null \
    || { echo "bucket $BUCKET exists without Object Lock; choose another name" >&2; exit 1; }
else
  if [ "$REGION" = us-east-1 ]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" --object-lock-enabled-for-bucket
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" --object-lock-enabled-for-bucket \
      --create-bucket-configuration "LocationConstraint=$REGION"
  fi
  aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  aws s3api put-object-lock-configuration --bucket "$BUCKET" --object-lock-configuration \
    "{\"ObjectLockEnabled\":\"Enabled\",\"Rule\":{\"DefaultRetention\":{\"Mode\":\"COMPLIANCE\",\"Years\":$RETENTION_YEARS}}}"
  echo "created s3://$BUCKET with versioning and $RETENTION_YEARS-year compliance retention"
fi

# ---------------------------------------------------------------- 2. IAM user and key
POLICY=$(jq -n --arg b "$BUCKET" '{
  Version: "2012-10-17",
  Statement: [
    {Effect: "Allow", Action: ["s3:PutObject", "s3:GetObject"], Resource: "arn:aws:s3:::\($b)/*"},
    {Effect: "Allow", Action: ["s3:ListBucket"], Resource: "arn:aws:s3:::\($b)"},
    {Effect: "Deny", Action: ["s3:DeleteObject", "s3:DeleteObjectVersion", "s3:PutObjectRetention",
      "s3:BypassGovernanceRetention", "s3:PutBucketObjectLockConfiguration", "s3:DeleteBucket"],
     Resource: ["arn:aws:s3:::\($b)", "arn:aws:s3:::\($b)/*"]}
  ]}')
aws iam get-user --user-name "$IAM_USER" >/dev/null 2>&1 || aws iam create-user --user-name "$IAM_USER" >/dev/null
aws iam put-user-policy --user-name "$IAM_USER" --policy-name fb-archive-no-delete --policy-document "$POLICY"
KEY=$(aws iam create-access-key --user-name "$IAM_USER")
KEY_ID=$(jq -r .AccessKey.AccessKeyId <<<"$KEY")
KEY_SECRET=$(jq -r .AccessKey.SecretAccessKey <<<"$KEY")
echo "created access key $KEY_ID for $IAM_USER (older keys, if any, are left in place)"

# ---------------------------------------------------------------- 3. repository secrets
gh secret set IC_ARCHIVE_S3_URI     --repo "$REPO" --body "s3://$BUCKET/$PREFIX"
gh secret set AWS_ACCESS_KEY_ID     --repo "$REPO" --body "$KEY_ID"
gh secret set AWS_SECRET_ACCESS_KEY --repo "$REPO" --body "$KEY_SECRET"
gh secret set AWS_DEFAULT_REGION    --repo "$REPO" --body "$REGION"
unset KEY KEY_SECRET
echo "stored the four secrets in $REPO"

# ---------------------------------------------------------------- 4. branch ruleset
NAME=protect-default-branch-history
if gh api "repos/$REPO/rulesets" --jq '.[].name' | grep -qx "$NAME"; then
  echo "ruleset $NAME already exists"
else
  gh api -X POST "repos/$REPO/rulesets" --input - >/dev/null <<EOF
{"name": "$NAME", "target": "branch", "enforcement": "active",
 "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
 "rules": [{"type": "non_fast_forward"}, {"type": "deletion"}],
 "bypass_actors": []}
EOF
  echo "added ruleset $NAME: no force pushes to or deletion of the default branch"
fi

# ---------------------------------------------------------------- first upload
DEFAULT=$(gh api "repos/$REPO" --jq .default_branch)
if gh api "repos/$REPO/contents/.github/workflows/fb-archive-offsite.yml?ref=$DEFAULT" >/dev/null 2>&1; then
  gh workflow run fb-archive-offsite.yml --repo "$REPO" --ref "$DEFAULT"
  echo "started fb-archive-offsite on $DEFAULT; follow it under Actions"
else
  echo "fb-archive-offsite.yml is not on $DEFAULT yet (merge PR #352); it runs on that merge"
fi
echo "done"
