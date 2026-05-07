# コンテナ起動時にgit logでタイムスタンプを復元します
git ls-files | while read file; do
  timestamp=$(git log -1 --format="%ai" -- "$file")
  touch -d "$timestamp" "$file"
done