# OpenSearch Fine-Grained Access Control - AWS Console Configuration

## Issue Summary

The OpenSearch domain `ids2-soc-domain` has Fine-Grained Access Control (FGAC) enabled, which requires IAM users to be mapped to internal OpenSearch roles. The HTTP Basic Auth method is not working because:

1. The internal user database requires additional configuration
2. The master user needs to be properly set up in the OpenSearch security plugin
3. The resource-based policy alone is not sufficient for FGAC

## Solution: Configure via AWS Console

This is the **recommended and easiest** method to configure FGAC.

### Step-by-Step Instructions

#### 1. Access AWS Console

1. Go to: https://console.aws.amazon.com/
2. Sign in with your AWS credentials
3. Navigate to **OpenSearch Service**
4. Select region: **us-east-1**

#### 2. Select Your Domain

1. Click on domain: **ids2-soc-domain**
2. Wait for the domain details page to load

#### 3. Configure Fine-Grained Access Control

1. Click on the **"Security configuration"** tab
2. Under **"Fine-grained access control"**, click **"Edit"**
3. You'll see the current configuration:
   - Master user: `admin`
   - Internal user database: Enabled

#### 4. Map IAM User to Role

1. Scroll down to **"Backend roles"** section
2. Click **"Add backend role"**
3. Enter the IAM ARN:
   ```
   arn:aws:iam::211125764416:user/alexis
   ```
4. Click **"Add"**

5. In the **"Role mapping"** section:
   - Select role: **`all_access`**
   - Add the backend role you just created
   - Click **"Save changes"**

#### 5. Wait for Changes to Apply

1. The domain will show **"Processing"** status
2. Wait 2-5 minutes for changes to propagate
3. Domain status will return to **"Active"**

#### 6. Verify Configuration

Run this test from your Raspberry Pi or development machine:

```bash
python3 deploy/test_opensearch_connection.py
```

Expected output:
```
✅ SigV4 auth successful!
✅ Cluster health check successful!
✅ Test index created successfully!
```

## Alternative Method: AWS CLI

If you prefer command-line configuration, you can use the AWS CLI to update the domain's advanced security options. However, this is more complex and the Console method is recommended.

### Using AWS CLI (Advanced)

```bash
# This updates the access policy but does NOT configure FGAC role mappings
# Role mappings must be done via Console or OpenSearch API

aws opensearch update-domain-config \
  --domain-name ids2-soc-domain \
  --profile moi33 \
  --region us-east-1 \
  --advanced-security-options \
    'Enabled=true,InternalUserDatabaseEnabled=true,MasterUserOptions={MasterUserARN=arn:aws:iam::211125764416:user/alexis}'
```

**Note**: This command updates the master user but does NOT create role mappings. You still need to use the Console or OpenSearch API to map the user to the `all_access` role.

## Alternative Method: OpenSearch Dashboards

If you have access to OpenSearch Dashboards:

1. Go to: `https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com/_dashboards`
2. Log in with master credentials: `admin` / `Admin123!`
3. Navigate to **Security** → **Roles**
4. Select role: **all_access**
5. Go to **"Mapped users"** tab
6. Click **"Map users"**
7. Add backend role: `arn:aws:iam::211125764416:user/alexis`
8. Click **"Map"**

## Troubleshooting

### "User: anonymous is not authorized"

**Cause**: IAM user not mapped to any OpenSearch role  
**Solution**: Follow the AWS Console steps above to map the user

### "403 Forbidden" with master credentials

**Cause**: Master user not properly configured or IP restriction  
**Solution**: Use AWS Console method instead

### "no permissions for [cluster:monitor/main]"

**Cause**: User mapped but to wrong role or role doesn't have permissions  
**Solution**: Ensure user is mapped to `all_access` role, not a custom role

### Changes not taking effect

**Cause**: Propagation delay  
**Solution**: Wait 5-10 minutes and try again

## Verification Checklist

After configuration, verify:

- [ ] Domain status is "Active" (not "Processing")
- [ ] IAM user ARN is listed in backend roles
- [ ] Backend role is mapped to `all_access` role
- [ ] Test script shows "✅ SigV4 auth successful!"
- [ ] Can query cluster health endpoint
- [ ] Can create/delete test indices

## Next Steps After Configuration

Once FGAC is properly configured:

1. **Test connectivity**:
   ```bash
   python3 deploy/test_opensearch_connection.py
   ```

2. **Deploy the full pipeline**:
   ```bash
   sudo ./deploy/deploy_and_test.sh
   ```

3. **Monitor in Grafana**:
   - URL: http://192.168.178.66:3000
   - Username: admin
   - Password: admin

## Security Best Practices

After initial setup:

1. **Rotate master password**:
   - Use AWS Console to update master user password
   - Store in AWS Secrets Manager
   - Remove from config files

2. **Use IAM authentication only**:
   - Configure Vector to use AWS SigV4
   - Configure Python agent to use boto3 credentials
   - Disable internal user database if not needed

3. **Enable audit logging**:
   - Track all access to the domain
   - Monitor for unauthorized access attempts

4. **Set up VPC access** (optional):
   - Move domain to VPC for additional security
   - Use VPC endpoints for private access

## References

- [AWS OpenSearch FGAC Documentation](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/fgac.html)
- [OpenSearch Security Plugin](https://opensearch.org/docs/latest/security/access-control/index/)
- [IAM Authentication for OpenSearch](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/fgac.html#fgac-walkthrough-iam)

---

**Status**: Awaiting FGAC configuration via AWS Console  
**Estimated Time**: 5-10 minutes  
**Difficulty**: Easy (point-and-click in Console)
