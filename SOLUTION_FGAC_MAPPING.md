# Solution: Configuration du Mapping de Rôles FGAC

## Problème Identifié

La page "Edit security configuration" ne montre PAS les options de mapping de rôles. Cette page configure uniquement:
- Le master user (IAM ARN ou username/password)
- Les méthodes d'authentification (SAML, JWT, Cognito, etc.)

**Les mappages de rôles doivent être configurés différemment.**

## Solution: Utiliser OpenSearch Dashboards

### Étape 1: Sauvegarder la Configuration Actuelle

1. Sur la page AWS Console actuelle, **ne changez rien**
2. Cliquez sur "Cancel" pour fermer cette page
3. Retournez à la page de détails du domaine

### Étape 2: Accéder à OpenSearch Dashboards

1. Allez sur la page de détails du domaine:
   https://us-east-1.console.aws.amazon.com/aos/home?region=us-east-1#opensearch/domains/ids2-soc-domain

2. Trouvez l'URL "OpenSearch Dashboards URL" (devrait être visible sur la page)
   
3. OU utilisez directement ce lien:
   https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com/_dashboards

### Étape 3: Se Connecter à OpenSearch Dashboards

Vous avez 2 options:

#### Option A: Connexion avec Master User (Recommandé)
- Username: `admin`
- Password: `Admin123!`

#### Option B: Connexion IAM (Si configuré)
- Cliquez sur "Log in with IAM"
- Utilisez vos credentials AWS

### Étape 4: Configurer le Mapping de Rôles

Une fois connecté à OpenSearch Dashboards:

1. **Menu de gauche** → Cliquez sur l'icône ☰ (hamburger menu)

2. **Security** → Cliquez sur "Security"

3. **Roles** → Cliquez sur "Roles"

4. **Trouvez "all_access"** → Cliquez sur le rôle "all_access"

5. **Mapped users** → Cliquez sur l'onglet "Mapped users"

6. **Manage mapping** → Cliquez sur "Manage mapping"

7. **Ajoutez le Backend Role**:
   - Dans le champ "Backend roles", ajoutez:
     ```
     arn:aws:iam::211125764416:user/alexis
     ```
   - Cliquez sur "Map"

8. **Sauvegardez** → Cliquez sur "Submit"

### Étape 5: Vérifier la Configuration

Après avoir configuré le mapping:

```bash
# Testez la connexion
python3 deploy/test_opensearch_connection.py
```

Résultat attendu:
```
✅ SigV4 auth successful!
✅ Cluster health check successful!
✅ Test index created successfully!
```

## Alternative: Utiliser l'API OpenSearch Directement

Si vous ne pouvez pas accéder à OpenSearch Dashboards, utilisez curl:

```bash
# Mapper l'IAM user au rôle all_access
curl -X PUT \
  "https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com/_plugins/_security/api/rolesmapping/all_access" \
  -u admin:Admin123! \
  -H 'Content-Type: application/json' \
  -d '{
    "backend_roles": ["arn:aws:iam::211125764416:user/alexis"],
    "users": ["admin"]
  }'
```

**Note**: Cette commande doit être exécutée depuis le Raspberry Pi (IP 192.168.178.66) si l'accès IP est restreint.

## Pourquoi la Page AWS Console Ne Montre Pas les Mappings?

La page "Edit security configuration" dans AWS Console configure:
- ✅ Le master user
- ✅ Les méthodes d'authentification
- ❌ PAS les mappages de rôles internes à OpenSearch

Les mappages de rôles sont une fonctionnalité **interne à OpenSearch** et doivent être configurés via:
1. OpenSearch Dashboards (interface graphique)
2. OpenSearch Security API (ligne de commande)
3. Terraform/CloudFormation (infrastructure as code)

## Résumé des Étapes

1. ❌ **Ne pas** utiliser la page "Edit security configuration" pour les mappings
2. ✅ **Utiliser** OpenSearch Dashboards → Security → Roles → all_access → Mapped users
3. ✅ **Ajouter** le backend role: `arn:aws:iam::211125764416:user/alexis`
4. ✅ **Tester** avec `python3 deploy/test_opensearch_connection.py`

## Liens Utiles

- **OpenSearch Dashboards**: https://search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com/_dashboards
- **Credentials**: admin / Admin123!
- **IAM ARN**: arn:aws:iam::211125764416:user/alexis
- **Rôle à mapper**: all_access

---

**Action Immédiate**: Fermez la page AWS Console actuelle et accédez à OpenSearch Dashboards pour configurer les mappings de rôles.
