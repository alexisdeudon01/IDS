# Final FGAC Configuration Steps

## Current Status
✅ You're on the correct page: "Edit security configuration"  
✅ IAM ARN is already entered: `arn:aws:iam::211125764416:user/alexis`  
✅ "Set IAM ARN as master user" is selected

## Next Steps (From Your Current Screen)

### Step 1: Scroll Down
Scroll down on the current page to find the **"Role mapping"** or **"Backend roles"** section.

### Step 2: Look for Role Mapping Section
You should see a section that allows you to map backend roles to OpenSearch roles. It might be labeled:
- "Map backend roles to roles"
- "Role mappings"
- "Backend role mappings"

### Step 3: Add Role Mapping
1. Find the **"all_access"** role in the list
2. Click "Edit" or "Add mapping" next to it
3. In the "Backend roles" field, add: `arn:aws:iam::211125764416:user/alexis`
4. Click "Add" or "Save"

### Alternative: If You Don't See Role Mapping Section

If the current page doesn't have role mapping options, you may need to:

1. **Save the current changes first** (click "Save changes" at the bottom)
2. Wait for the domain to finish processing (2-3 minutes)
3. Go back to the domain details page
4. Look for **"Security"** or **"Access control"** tab
5. Find **"Role mappings"** or **"Manage role mappings"**
6. Map the IAM ARN to the `all_access` role

### Step 4: Save and Wait
1. Click "Save changes" at the bottom of the page
2. Domain status will change to "Processing"
3. Wait 2-5 minutes for changes to apply
4. Domain status will return to "Active"

### Step 5: Verify
Run this command to test:
```bash
python3 deploy/test_opensearch_connection.py
```

Expected output:
```
✅ SigV4 auth successful!
✅ Cluster health check successful!
```

## Troubleshooting

### If "Set IAM ARN as master user" is the only option:
This sets the IAM user as the master user, which gives full access. This should work, but you may still need to configure role mappings separately.

**After saving:**
1. Go to OpenSearch Dashboards: https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com/_dashboards
2. You should be able to log in automatically (IAM auth)
3. Go to Security → Roles → all_access → Mapped users
4. Verify your IAM ARN is listed

### If you get errors:
- Make sure "Enable fine-grained access control" checkbox is checked
- Make sure the IAM ARN format is correct: `arn:aws:iam::211125764416:user/alexis`
- Try using "Create master user" option instead and create a username/password

## Quick Reference

**IAM ARN**: `arn:aws:iam::211125764416:user/alexis`  
**Role to map to**: `all_access`  
**Domain**: ids2-soc-domain  
**Region**: us-east-1

---

**Need help?** The screenshot shows you're on the right page. Just scroll down to find role mapping options, or save the current changes and access role mappings from the domain details page.
