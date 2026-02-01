#!/bin/bash
# ============================================================================
# IDS2 SOC Pipeline - Create PUBLIC AWS OpenSearch Domain
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}IDS2 SOC Pipeline - Create PUBLIC OpenSearch Domain${NC}"
echo -e "${GREEN}============================================================================${NC}"

# Configuration
DOMAIN_NAME="ids2-soc-domain"
AWS_PROFILE="moi33"
AWS_REGION="us-east-1"
INSTANCE_TYPE="t3.small.search"  # Smallest instance for cost savings
INSTANCE_COUNT=1
EBS_VOLUME_SIZE=10  # GB
MASTER_USER="admin"
MASTER_PASSWORD="Admin123!"  # Change this!

echo -e "${YELLOW}Domain Configuration:${NC}"
echo -e "  Domain Name: $DOMAIN_NAME"
echo -e "  AWS Profile: $AWS_PROFILE"
echo -e "  AWS Region: $AWS_REGION"
echo -e "  Instance Type: $INSTANCE_TYPE"
echo -e "  Instance Count: $INSTANCE_COUNT"
echo -e "  EBS Volume: ${EBS_VOLUME_SIZE}GB"
echo -e "  Access: ${RED}PUBLIC (Internet accessible)${NC}"
echo ""

echo -e "${RED}WARNING: This will create a PUBLIC OpenSearch domain!${NC}"
echo -e "${RED}The domain will be accessible from the internet.${NC}"
echo -e "${RED}Make sure to use strong credentials and IP restrictions.${NC}"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${YELLOW}Aborted${NC}"
    exit 0
fi

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo -e "${YELLOW}Install with: pip install awscli${NC}"
    exit 1
fi

# Check if profile exists
if ! aws configure list --profile $AWS_PROFILE &> /dev/null; then
    echo -e "${RED}Error: AWS profile '$AWS_PROFILE' not found${NC}"
    echo -e "${YELLOW}Configure with: aws configure --profile $AWS_PROFILE${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 1: Checking if domain already exists...${NC}"

# Check if domain exists
DOMAIN_STATUS=$(aws opensearch describe-domain \
    --domain-name $DOMAIN_NAME \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'DomainStatus.DomainName' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$DOMAIN_STATUS" != "NOT_FOUND" ]; then
    echo -e "${YELLOW}Domain '$DOMAIN_NAME' already exists${NC}"
    
    # Get domain endpoint
    ENDPOINT=$(aws opensearch describe-domain \
        --domain-name $DOMAIN_NAME \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --query 'DomainStatus.Endpoint' \
        --output text)
    
    echo -e "${GREEN}Domain Endpoint: https://$ENDPOINT${NC}"
    echo ""
    echo -e "${YELLOW}To delete and recreate, run:${NC}"
    echo -e "  aws opensearch delete-domain --domain-name $DOMAIN_NAME --profile $AWS_PROFILE --region $AWS_REGION"
    exit 0
fi

echo -e "${GREEN}✓ Domain does not exist, proceeding with creation${NC}"

echo ""
echo -e "${YELLOW}Step 2: Creating OpenSearch domain (this takes 10-15 minutes)...${NC}"

# Create the domain
aws opensearch create-domain \
    --domain-name $DOMAIN_NAME \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --engine-version "OpenSearch_2.11" \
    --cluster-config \
        InstanceType=$INSTANCE_TYPE,InstanceCount=$INSTANCE_COUNT \
    --ebs-options \
        EBSEnabled=true,VolumeType=gp3,VolumeSize=$EBS_VOLUME_SIZE \
    --access-policies '{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "AWS": "*"
                },
                "Action": "es:*",
                "Resource": "arn:aws:es:'$AWS_REGION':*:domain/'$DOMAIN_NAME'/*",
                "Condition": {
                    "IpAddress": {
                        "aws:SourceIp": ["192.168.178.66/32"]
                    }
                }
            }
        ]
    }' \
    --advanced-security-options \
        Enabled=true,InternalUserDatabaseEnabled=true,MasterUserOptions={MasterUserName=$MASTER_USER,MasterUserPassword=$MASTER_PASSWORD} \
    --node-to-node-encryption-options Enabled=true \
    --encryption-at-rest-options Enabled=true \
    --domain-endpoint-options EnforceHTTPS=true,TLSSecurityPolicy=Policy-Min-TLS-1-2-2019-07 \
    --no-cli-pager

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Domain creation initiated${NC}"
else
    echo -e "${RED}Error: Failed to create domain${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 3: Waiting for domain to become active...${NC}"
echo -e "${YELLOW}This typically takes 10-15 minutes. Please wait...${NC}"

# Wait for domain to be active
WAIT_COUNT=0
MAX_WAIT=60  # 60 iterations * 15 seconds = 15 minutes

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    PROCESSING=$(aws opensearch describe-domain \
        --domain-name $DOMAIN_NAME \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --query 'DomainStatus.Processing' \
        --output text 2>/dev/null || echo "true")
    
    if [ "$PROCESSING" = "false" ]; then
        echo -e "${GREEN}✓ Domain is active!${NC}"
        break
    fi
    
    echo -e "${YELLOW}Still processing... ($((WAIT_COUNT * 15)) seconds elapsed)${NC}"
    sleep 15
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo -e "${RED}Timeout waiting for domain to become active${NC}"
    echo -e "${YELLOW}Check status with:${NC}"
    echo -e "  aws opensearch describe-domain --domain-name $DOMAIN_NAME --profile $AWS_PROFILE --region $AWS_REGION"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 4: Getting domain information...${NC}"

# Get domain details
ENDPOINT=$(aws opensearch describe-domain \
    --domain-name $DOMAIN_NAME \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'DomainStatus.Endpoint' \
    --output text)

ARN=$(aws opensearch describe-domain \
    --domain-name $DOMAIN_NAME \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'DomainStatus.ARN' \
    --output text)

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}OpenSearch Domain Created Successfully!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${BLUE}Domain Details:${NC}"
echo -e "  Name: $DOMAIN_NAME"
echo -e "  Endpoint: ${GREEN}https://$ENDPOINT${NC}"
echo -e "  ARN: $ARN"
echo -e "  Region: $AWS_REGION"
echo -e "  Master User: $MASTER_USER"
echo -e "  Master Password: $MASTER_PASSWORD"
echo ""
echo -e "${BLUE}Access Configuration:${NC}"
echo -e "  Type: ${RED}PUBLIC${NC}"
echo -e "  Allowed IP: 192.168.178.66/32 (your Raspberry Pi)"
echo -e "  HTTPS: Enforced"
echo -e "  TLS: 1.2+"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Update config.yaml with the endpoint:"
echo -e "     ${GREEN}opensearch_endpoint: \"https://$ENDPOINT\"${NC}"
echo ""
echo -e "  2. Test connection from Raspberry Pi:"
echo -e "     ${GREEN}curl -u $MASTER_USER:$MASTER_PASSWORD https://$ENDPOINT${NC}"
echo ""
echo -e "  3. Access OpenSearch Dashboards:"
echo -e "     ${GREEN}https://$ENDPOINT/_dashboards${NC}"
echo ""
echo -e "${YELLOW}To delete this domain:${NC}"
echo -e "  aws opensearch delete-domain --domain-name $DOMAIN_NAME --profile $AWS_PROFILE --region $AWS_REGION"
echo ""
echo -e "${RED}IMPORTANT: This is a PUBLIC domain. Keep your credentials secure!${NC}"
echo ""
