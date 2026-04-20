# Upstream RDGen + yama: (1) GitHub 204 boş gövde (2) GithubRun.id zorunlu PK
# (3) entrypoint: volume izinleri (temp_zips Permission denied gider)
FROM bryangerlach/rdgen:latest

USER root

COPY apply_patch.py /tmp/apply_patch.py
RUN python3 /tmp/apply_patch.py && rm /tmp/apply_patch.py \
    && python3 -c "t=open('/opt/rdgen/rdgenerator/views.py',encoding='utf-8').read(); \
    assert '_rdgen_pub' in t and '_rdgen_next_pk' in t and 'except ValueError:' in t and 'github_data = {}' in t, 'yama uygulanmamis'"

RUN set -eux; \
    if command -v apt-get >/dev/null 2>&1; then \
      apt-get update && apt-get install -y --no-install-recommends gosu \
      && rm -rf /var/lib/apt/lists/*; \
    elif command -v apk >/dev/null 2>&1; then \
      apk add --no-cache su-exec; \
    fi

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown root:root /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
