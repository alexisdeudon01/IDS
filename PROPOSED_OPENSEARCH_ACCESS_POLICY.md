# Proposed OpenSearch Access Policy Options

## Current Situation
- **Current Policy**: IAM-only (allows `arn:aws:iam::211125764416:user/alexis`)
- **Issue**: Vector container cannot authenticate because it's running in Docker without proper AWS credential chain
- **Result**: Vector health check fails, cannot send data to OpenSearch

---

## 🔧 Proposed Solutions (Choose One)

### Option 1: Add IP-Based Allow for All Operations (Simplest)
**Pros**: 
- No 403 errors
- Works immediately
- Simple to implement

**Cons**:
- Less secure (allows any request from specified IPs)
- Requires maintaining IP whitelist

**Proposed Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowIAMUserAlexis",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::211125764416:user/alexis"
      },
      "Action": "es:*",
      "Resource": "arn:aws:es:us-east-1:211125764416:domain/ids2-soc-domain/*"
    },
    {
      "Sid": "AllowFromTrustedIPs",
      "Effect": "Allow",
      "Principal": {
        "AWS": "*"
      },
      "Action": "es:*",
      "Resource": "arn:aws:es:us-east-1:211125764416:domain/ids2-soc-domain/*",
      "Condition": {
        "IpAddress": {
          "aws:SourceIp": [
            "188.115.7.67/32",      # Current development IP
            "192.168.178.66/32"     # Raspberry Pi IP
          ]
        }
      }
    }
  ]
}
```

**Use Case**: Development/testing environments, home lab setups

---

### Option 2: Public Access with FGAC Only (Most Permissive)
**Pros**:
- No IP restrictions
- No 403 errors from resource policy
- FGAC still provides security layer

**Cons**:
- Relies entirely on FGAC for security
- Exposed to internet (but FGAC protects)

**Proposed Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "*"
      },
      "Action": "es:*",
      "Resource": "arn:aws:es:us-east-1:211125764416:domain/ids2-soc-domain/*"
    }
  ]
}
```

**Security Note**: FGAC will still require authentication (admin/password or IAM), so not truly "open"

**Use Case**: When you want FGAC to be the only security layer

---

### Option 3: Hybrid - IAM + IP for HTTP Operations
**Pros**:
- Balanced security
- Allows Vector from specific IPs
- Maintains IAM for administrative access

**Cons**:
- More complex policy
- Requires IP maintenance

**Proposed Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowIAMUserAlexis",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::211125764416:user/alexis"
      },
      "Action": "es:*",
      "Resource": "arn:aws:es:us-east-1:211125764416:domain/ids2-soc-domain/*"
    },
    {
      "Sid": "AllowHTTPFromTrustedIPs",
      "Effect": "Allow",
      "Principal": {
        "AWS": "*"
      },
      "Action": [
        "es:ESHttpGet",
        "es:ESHttpHead",
        "es:ESHttpPost",
        "es:ESHttpPut",
        "es:ESHttpDelete"
      ],
      "Resource": "arn:aws:es:us-east-1:211125764416:domain/ids2-soc-domain/*",
      "Condition": {
        "IpAddress": {
          "aws:SourceIp": [
            "188.115.7.67/32",
            "192.168.178.66/32"
          ]
        }
      }
    }
  ]
}
```

**Use Case**: Production with known source IPs

---

### Option 4: VPC-Based Access (Most Secure - Requires VPC)
**Pros**:
- Most secure
- No public internet exposure
- No IP whitelisting needed

**Cons**:
- Requires VPC deployment
- More complex setup
- May require domain recreation

**Proposed Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "*"
      },
      "Action": "es:*",
      "Resource": "arn:aws:es:us-east-1:211125764416:domain/ids2-soc-domain/*"
    }
  ]
}
```

**Additional Requirements**:
- Deploy OpenSearch in VPC
- Configure security groups
- Setup VPN or Direct Connect for Raspberry Pi access

**Use Case**: Enterprise production environments

---

## 🎯 Recommended Solution for Your Use Case

### For Raspberry Pi Home Lab: **Option 1** (IP-Based Allow)

**Reasoning**:
1. Simple to implement
2. Works with Vector in Docker
3. Secure enough for home lab (trusted IPs only)
4. No VPC complexity
5. Maintains IAM access for administration

**Implementation Command** (DO NOT RUN - PROPOSAL ONLY):
```bash
aws opensearch update-domain-config \
  --domain-name ids2-soc-domain \
  --profile moi33 \
  --region us-east-1 \
  --access-policies '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "AllowIAMUserAlexis",
        "Effect": "Allow",
        "Principal": {"AWS": "arn:aws:iam::211125764416:user/alexis"},
        "Action": "es:*",
        "Resource": "arn:aws:es:us-east-1:211125764416:domain/ids2-soc-domain/*"
      },
      {
        "Sid": "AllowFromRaspberryPi",
        "Effect": "Allow",
        "Principal": {"AWS": "*"},
        "Action": "es:*",
        "Resource": "arn:aws:es:us-east-1:211125764416:domain/ids2-soc-domain/*",
        "Condition": {
          "IpAddress": {
            "aws:SourceIp": ["192.168.178.66/32"]
          }
        }
      }
    ]
  }'
```

---

## 📊 Comparison Matrix

| Option | Security | Complexity | Vector Support | Admin Access | Best For |
|--------|----------|------------|----------------|--------------|----------|
| Option 1 (IP Allow) | ⭐⭐⭐ | ⭐ | ✅ Yes | ✅ IAM + IP | Home Lab |
| Option 2 (Public + FGAC) | ⭐⭐ | ⭐ | ✅ Yes | ✅ FGAC only | Testing |
| Option 3 (Hybrid) | ⭐⭐⭐⭐ | ⭐⭐ | ✅ Yes | ✅ IAM + IP | Small Prod |
| Option 4 (VPC) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ Yes | ✅ IAM | Enterprise |

---

## 🔍 Testing After Policy Change

After applying any policy, test with:

```bash
# Test 1: From development machine (IAM)
python3 deploy/test_opensearch_connection.py

# Test 2: From Raspberry Pi (IP-based)
curl -X GET "https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com/"

# Test 3: Vector ingestion
python3 deploy/vector_e2e_test.py
```

---

## ⚠️ Important Notes

1. **Wait Time**: Policy changes take 5-15 minutes to propagate
2. **IP Changes**: If Raspberry Pi IP changes, update policy
3. **FGAC**: Still active - provides authentication layer
4. **Monitoring**: Enable CloudWatch logs to monitor access

---

## 🚀 Next Steps

1. **Review** this proposal
2. **Choose** the option that fits your security requirements
3. **Confirm** the IP addresses to whitelist
4. **Request** implementation if you want me to apply the policy
5. **Test** after implementation

---

**Status**: 📋 **PROPOSAL ONLY - NOT IMPLEMENTED**  
**Recommendation**: Option 1 (IP-Based Allow for Raspberry Pi)  
**Awaiting**: Your decision on which option to implement
