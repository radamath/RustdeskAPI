# Upstream RDGen + yama: (1) GitHub 204 boş gövde (2) GithubRun.id zorunlu PK
FROM bryangerlach/rdgen:latest
USER root
COPY apply_patch.py /tmp/apply_patch.py
RUN python3 /tmp/apply_patch.py && rm /tmp/apply_patch.py \
    && python3 -c "t=open('/opt/rdgen/rdgenerator/views.py',encoding='utf-8').read(); \
assert '_rdgen_next_pk' in t and 'except ValueError:' in t and 'github_data = {}' in t, 'yama uygulanmamis'"
USER user
