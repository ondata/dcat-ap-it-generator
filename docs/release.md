# Release

Procedura per pubblicare una nuova versione su GitHub e PyPI.

## Step

**1. Bump versione**

Aggiornare il campo `version` in `pyproject.toml`:

```toml
version = "X.Y.Z"
```

**2. Aggiornare LOG.md**

Aggiungere una sezione con la data corrente e i cambiamenti principali.

**3. Commit**

```bash
git add pyproject.toml LOG.md <altri file modificati>
git commit -m "feat/fix/...: descrizione, bump vX.Y.Z"
```

**4. Build**

```bash
uv build
```

Produce `dist/dcat_ap_it_generator-X.Y.Z-py3-none-any.whl` e `dist/dcat_ap_it_generator-X.Y.Z.tar.gz`.

**5. Tag e push**

```bash
git push
git tag vX.Y.Z
git push origin vX.Y.Z
```

**6. GitHub release**

```bash
gh release create vX.Y.Z \
  dist/dcat_ap_it_generator-X.Y.Z.tar.gz \
  dist/dcat_ap_it_generator-X.Y.Z-py3-none-any.whl \
  --title "vX.Y.Z" \
  --notes "- punto 1
- punto 2"
```

**7. Pubblicazione su PyPI**

```bash
twine upload dist/dcat_ap_it_generator-X.Y.Z*
```

**8. Aggiornamento CLI locale**

```bash
uv tool install -e . --reinstall
```
