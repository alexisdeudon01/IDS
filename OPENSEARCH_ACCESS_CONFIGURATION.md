# OpenSearch Domain Access Configuration Guide

## Current Status

✅ **OpenSearch Domain Created Successfully**
- Domain Name: `ids2-soc-domain`
- Endpoint: `https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com`
- Status: **ACTIVE** (Processing: false)
- Engine Version: OpenSearch 2.11
- Instance Type: t3.small.search
- Storage: 10GB gp3 EBS

✅ **Fine-Grained Access Control (FGAC) Enabled**
- Master Username: `admin`
- Master Password: `Admin123!`
- Internal User Database: Enabled
- Anonymous Auth: Disabled

✅ **Resource-Based Access Policy Updated**
- IAM User: `arn:aws:iam::211125764416:user/alexis`
- Permissions: `es:*` (full access)
- IP Restriction: `192.168.178.66/32` (Raspberry Pi IP)

## Current Issue

The domain has **two layers of access control**:

1. **Resource-Based Policy** (AWS IAM level) ✅ CONFIGURED
   - Controls who can access the domain from AWS perspective
   - Currently allows IAM user `alexis` with full permissions
   - Restricts access to IP `192.168.178.66/32`

2. **Fine-Grained Access Control** (OpenSearch internal) ❌ NOT CONFIGURED
   - Controls permissions within OpenSearch itself
   - Requires mapping IAM users to OpenSearch roles
   - Can only be configured using master credentials from allowed IP

## Why Current Tests Fail

### From Development Machine (Current Location)
- ❌ **IP Not Allowed**: Current IP is not `192.168.178.66/32`
- ❌ **Cannot Use Master Credentials**: HTTP Basic Auth blocked by IP restriction
- ❌ **Cannot Use IAM SigV4**: IAM user not mapped to OpenSearch role

### What Works
- ✅ Domain is reachable (returns 403, not timeout)
- ✅ TLS/SSL working correctly
- ✅ AWS credentials valid
- ✅ Resource policy applied

## Solution: Configure from Raspberry Pi

The Fine-Grained Access Control **must be configured from the Raspberry Pi** (IP: 192.168.178.66) because:

1. Only this IP can use master credentials
2. Master credentials are required to map IAM users to roles
3. Once mapped, IAM SigV4 auth will work from any IP

## Step-by-Step Configuration (On Raspberry Pi)

### Option 1: Automated Script (Recommended)

```bash
# On Raspberry Pi (192.168.178.66)
cd ~/ids2-soc-pipeline
python3 deploy/configure_opensearch_access.py
```

This script will:
1. Connect using master credentials (admin/Admin123!)
2. Map IAM user `arn:aws:iam::211125764416:user/alexis` to `all_access` role
3. Verify IAM user can now access the domain
4. Update `config.yaml` with the endpoint

### Option 2: Manual Configuration

```bash
# On Raspberry Pi (192.168.178.66)

# 1. Test basic connectivity
curl -u admin:Admin123! \
  https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com

# 2. Get current role mapping
curl -u admin:Admin123! \
  https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com/_plugins/_security/api/rolesmapping/all_access

# 3. Map IAM user to all_access role
curl -u admin:Admin123! -X PUT \
  https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com/_plugins/_security/api/rolesmapping/all_access \
  -H 'Content-Type: application/json' \
  -d '{
    "backend_roles": ["arn:aws:iam::211125764416:user/alexis"],
    "users": ["admin"]
  }'

# 4. Verify IAM access works
python3 deploy/test_opensearch_connection.py
```

### Option 3: Using AWS Console

1. Go to AWS OpenSearch Console
2. Select domain `ids2-soc-domain`
3. Click "Security configuration"
4. Under "Fine-grained access control", click "Manage"
5. Map IAM user `arn:aws:iam::211125764416:user/alexis` to `all_access` role

## After Configuration

Once the IAM user is mapped to the `all_access` role:

✅ **IAM SigV4 Authentication Will Work From Any IP**
- The Python agent can use AWS credentials
- No need to hardcode master username/password
- More secure (uses temporary credentials)
- Works with IAM roles and policies

✅ **Vector Can Send Logs**
- Vector will use AWS SigV4 authentication
- Configured in `vector/vector.toml`
- Uses AWS credentials from environment or instance profile

## Testing After Configuration

```bash
# On Raspberry Pi (after configuration)
python3 deploy/test_opensearch_connection.py
```

Expected output:
```
✅ SigV4 auth successful!
✅ Cluster health check successful!
✅ Test index created successfully!
✅ OpenSearch domain is accessible and functional!
```

## Configuration Files Updated

### config.yaml
```yaml
aws:
  profile: "moi33"
  region: "us-east-1"
  opensearch_domain: "ids2-soc-domain"
  opensearch_endpoint: "https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com"
```

### vector/vector.toml
```toml
[sinks.opensearch]
type = "elasticsearch"
endpoint = "https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com"
auth.strategy = "aws"
auth.region = "us-east-1"
```

## Security Considerations

### Current Setup (IP Restriction)
- ✅ Only Raspberry Pi can use master credentials
- ✅ Prevents unauthorized access from other IPs
- ❌ Limits where you can manage the domain

### Recommended for Production
1. **Remove IP Restriction** after IAM mapping is complete
2. **Use IAM SigV4 Only** (no master credentials in code)
3. **Rotate Master Password** and store in AWS Secrets Manager
4. **Enable VPC Access** for additional security layer
5. **Enable Audit Logging** to track all access

## Troubleshooting

### "User: anonymous is not authorized"
- **Cause**: IAM user not mapped to OpenSearch role
- **Solution**: Run configuration script from Raspberry Pi

### "403 Forbidden" with master credentials
- **Cause**: Not connecting from allowed IP (192.168.178.66)
- **Solution**: Run commands from Raspberry Pi

### "Connection timeout"
- **Cause**: Domain not accessible or network issue
- **Solution**: Check security groups, VPC settings, DNS resolution

### "no permissions for [cluster:monitor/main]"
- **Cause**: IAM user mapped but role doesn't have permissions
- **Solution**: Ensure user is mapped to `all_access` role, not a custom role

## Next Steps

1. **On Raspberry Pi**: Run `python3 deploy/configure_opensearch_access.py`
2. **Verify Access**: Run `python3 deploy/test_opensearch_connection.py`
3. **Update Config**: Endpoint will be automatically added to `config.yaml`
4. **Test Pipeline**: Run `python3 python_env/agent_mp.py` to test full pipeline
5. **Monitor**: Access Grafana at `http://localhost:3000` (admin/admin)

## References

- [OpenSearch Fine-Grained Access Control](https://opensearch.org/docs/latest/security/access-control/index/)
- [AWS OpenSearch IAM Authentication](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/fgac.html)
- [Vector AWS Authentication](https://vector.dev/docs/reference/configuration/sinks/elasticsearch/#auth.strategy)

---

**Status**: Domain created and active, awaiting FGAC configuration from Raspberry Pi  
**Next Action**: Run configuration script from IP 192.168.178.66
