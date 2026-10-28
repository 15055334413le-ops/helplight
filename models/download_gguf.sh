#!/bin/bash
# 分块下载 Spark-X2.6-4B-Q4_K_M.gguf（长连接易被代理掐断，故用 HTTP Range 分块 + 逐块校验）
set -u
cd "$(dirname "$0")"
URL='https://huggingface.co/XHToken/Spark-X2.6-4B-GGUF/resolve/fe31f8d64890302cc3a1d365d700357b4b75ba77/Spark-X2.6-4B-Q4_K_M.gguf'
TOTAL=3543441312
CHUNK=200000000
OUT='Spark-X2.6-4B-Q4_K_M.gguf'
mkdir -p chunks
n=$(( (TOTAL + CHUNK - 1) / CHUNK ))
for i in $(seq 0 $((n-1))); do
  start=$(( i * CHUNK ))
  end=$(( start + CHUNK - 1 )); [ $end -ge $TOTAL ] && end=$(( TOTAL - 1 ))
  want=$(( end - start + 1 ))
  f=$(printf 'chunks/part-%02d' $i)
  have=$(stat -c %s "$f" 2>/dev/null || echo 0)
  if [ "$have" = "$want" ]; then echo "part $i ok (cached)"; continue; fi
  ok=0
  for try in 1 2 3 4 5; do
    curl -sfL -r ${start}-${end} -o "$f" "$URL" || true
    have=$(stat -c %s "$f" 2>/dev/null || echo 0)
    if [ "$have" = "$want" ]; then ok=1; break; fi
    echo "part $i try $try size $have != $want, retrying"; sleep 2
  done
  [ $ok = 1 ] || { echo "FAILED part $i"; exit 1; }
  echo "part $i ok ($want bytes)"
done
cat chunks/part-* > "$OUT"
size=$(stat -c %s "$OUT"); echo "merged size: $size (want $TOTAL)"
[ "$size" = "$TOTAL" ] || { echo 'SIZE MISMATCH'; exit 1; }
sha256sum "$OUT"
echo 'expected sha256: 91cb2811aebb47ac916aa619d27d4cdd7f4143106b7917accb8ead4cd7f5cbd9'
