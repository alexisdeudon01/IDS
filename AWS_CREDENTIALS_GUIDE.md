# AWS Credentials Configuration Guide

## 📍 Location

AWS credentials for the IDS2 SOC Pipeline are stored in the standard AWS CLI location:

```
~/.aws/
├── config          # AWS configuration (regions, profiles)
└── credentials     # AWS access keys (secrets)
```

## 🔐 File Structure

### 1. `~/.aws/config`

Contains AWS configuration settings including regions and named profiles.

```ini
[default]
region = eu-central-1

[profile moi33]
region = us-east-1
```

**Fields**:
- `region`: AWS region for API calls
- `[profile NAME]`: Named profile for different AWS accounts/configurations

### 2. `~/.aws/credentials`

Contains AWS access credentials (NEVER commit to git!).

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY

[moi33]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
```

**Fields**:
- `aws_access_key_id`: Your AWS access key ID
- `aws_secret_access_key`: Your AWS secret access key
- `[PROFILE_NAME]`: Named profile matching config file

## 🔗 Integration with IDS2 Pipeline

### 1. Configuration File (`config.yaml`)

```yaml
aws:
  profile: "moi33"           # Profile name from ~/.aws/credentials
  region: "us-east-1"        # AWS region
  opensearch_domain: "ids2-soc-domain"
  opensearch_endpoint: ""    # Auto-detected
```

### 2. Docker Compose (`docker/docker-compose.yml`)

The AWS credentials directory is mounted into the container:

```yaml
services:
  ids2-agent:
    volumes:
      # Mount AWS credentials (read-only for security)
      - ~/.aws:/home/ids2user/.aws:ro
    
    environment:
      # Specify which profile to use
      - AWS_PROFILE=moi33
```

**Security Notes**:
- Mounted as **read-only** (`:ro`) to prevent modification
- Mapped to container user's home directory
- Profile specified via environment variable

### 3. Python Code (`python_env/modules/aws_manager.py`)

```python
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

class AWSManager:
    def __init__(self, config):
        self.config = config
        
        # Create session with named profile
        self.session = boto3.Session(
            profile_name=self.config.get('aws.profile')
        )
        
        # Create OpenSearch client
        self.opensearch_client = self.session.client(
            'opensearch',
            region_name=self.config.get('aws.region')
        )
```

## 🛠️ Setup Instructions

### Option 1: AWS CLI Configuration (Recommended)

```bash
# Install AWS CLI
sudo apt-get install awscli

# Configure default profile
aws configure
# Enter: Access Key ID, Secret Access Key, Region, Output format

# Configure named profile
aws configure --profile moi33
# Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output format
```

### Option 2: Manual File Creation

```bash
# Create AWS directory
mkdir -p ~/.aws
chmod 700 ~/.aws

# Create config file
cat > ~/.aws/config << 'EOF'
[default]
region = eu-central-1

[profile moi33]
region = us-east-1
EOF

# Create credentials file
cat > ~/.aws/credentials << 'EOF'
[default]
aws_access_key_id = YOUR_DEFAULT_ACCESS_KEY
aws_secret_access_key = YOUR_DEFAULT_SECRET_KEY

[moi33]
aws_access_key_id = YOUR_MOI33_ACCESS_KEY
aws_secret_access_key = YOUR_MOI33_SECRET_KEY
EOF

# Set proper permissions (important for security!)
chmod 600 ~/.aws/credentials
chmod 644 ~/.aws/config
```

## 🔍 Verification

### Test AWS Credentials

```bash
# Test default profile
aws sts get-caller-identity

# Test named profile
aws sts get-caller-identity --profile moi33

# Expected output:
# {
#     "UserId": "AIDAXXXXXXXXXXXXXXXXX",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/username"
# }
```

### Test OpenSearch Access

```bash
# List OpenSearch domains
aws opensearch list-domain-names --profile moi33 --region us-east-1

# Describe specific domain
aws opensearch describe-domain \
  --domain-name ids2-soc-domain \
  --profile moi33 \
  --region us-east-1
```

### Test from Python

```python
import boto3

# Test credentials
session = boto3.Session(profile_name='moi33')
sts = session.client('sts')
identity = sts.get_caller_identity()
print(f"Account: {identity['Account']}")
print(f"User: {identity['Arn']}")

# Test OpenSearch access
opensearch = session.client('opensearch', region_name='us-east-1')
domains = opensearch.list_domain_names()
print(f"Domains: {domains['DomainNames']}")
```

## 🔒 Security Best Practices

### 1. File Permissions

```bash
# Credentials should be readable only by owner
chmod 600 ~/.aws/credentials

# Config can be slightly more permissive
chmod 644 ~/.aws/config

# Directory should be accessible only by owner
chmod 700 ~/.aws
```

### 2. Never Commit Credentials

The `.gitignore` should include:

```gitignore
# AWS credentials
.aws/
*.pem
*.key
credentials
```

### 3. Use IAM Roles (Production)

For production deployments on EC2/ECS, use IAM roles instead of access keys:

```python
# No profile needed - uses instance role
session = boto3.Session()
```

### 4. Rotate Keys Regularly

```bash
# Create new access key
aws iam create-access-key --user-name your-username

# Update credentials file with new key
# Delete old access key
aws iam delete-access-key --access-key-id OLD_KEY_ID --user-name your-username
```

### 5. Use MFA (Multi-Factor Authentication)

For sensitive operations, require MFA:

```python
# Get session token with MFA
sts = boto3.client('sts')
response = sts.get_session_token(
    DurationSeconds=3600,
    SerialNumber='arn:aws:iam::123456789012:mfa/user',
    TokenCode='123456'  # MFA code
)

# Use temporary credentials
session = boto3.Session(
    aws_access_key_id=response['Credentials']['AccessKeyId'],
    aws_secret_access_key=response['Credentials']['SecretAccessKey'],
    aws_session_token=response['Credentials']['SessionToken']
)
```

## 🚨 Troubleshooting

### Error: "Unable to locate credentials"

```bash
# Check if credentials file exists
ls -la ~/.aws/credentials

# Check file permissions
ls -l ~/.aws/credentials

# Verify profile name
cat ~/.aws/credentials | grep -A 2 "\[moi33\]"

# Test with AWS CLI
aws sts get-caller-identity --profile moi33
```

### Error: "The security token included in the request is invalid"

```bash
# Credentials may be expired or incorrect
# Regenerate access keys in AWS IAM console
# Update ~/.aws/credentials with new keys
```

### Error: "Access Denied"

```bash
# Check IAM permissions
aws iam get-user --profile moi33

# Verify user has required permissions:
# - opensearch:*
# - ec2:DescribeInstances (if needed)
# - logs:* (if using CloudWatch)
```

### Docker Container Can't Access Credentials

```bash
# Verify volume mount in docker-compose.yml
docker-compose config | grep -A 5 "volumes:"

# Check file permissions
ls -la ~/.aws/

# Verify environment variable
docker-compose exec ids2-agent env | grep AWS_PROFILE

# Test from inside container
docker-compose exec ids2-agent aws sts get-caller-identity
```

## 📝 Required IAM Permissions

The AWS user/role needs these permissions for the IDS2 pipeline:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "opensearch:DescribeDomain",
        "opensearch:ListDomainNames",
        "opensearch:ESHttpGet",
        "opensearch:ESHttpPost",
        "opensearch:ESHttpPut",
        "opensearch:ESHttpDelete"
      ],
      "Resource": "arn:aws:es:us-east-1:*:domain/ids2-soc-domain"
    },
    {
      "Effect": "Allow",
      "Action": [
        "opensearch:CreateDomain",
        "opensearch:DeleteDomain",
        "opensearch:UpdateDomainConfig"
      ],
      "Resource": "arn:aws:es:us-east-1:*:domain/ids2-soc-domain"
    }
  ]
}
```

## 🔄 Environment Variables (Alternative)

Instead of using profiles, you can use environment variables:

```bash
export AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="YOUR_SECRET_KEY"
export AWS_DEFAULT_REGION="us-east-1"
```

In Docker Compose:

```yaml
environment:
  - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
  - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
  - AWS_DEFAULT_REGION=us-east-1
```

**Note**: This is less secure than using credential files with proper permissions.

## 📚 Additional Resources

- [AWS CLI Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [Boto3 Credentials](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [OpenSearch Service](https://docs.aws.amazon.com/opensearch-service/)
