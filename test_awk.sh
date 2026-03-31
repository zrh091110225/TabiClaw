awk -v date="2026-03-31" -v city="上海" -v price="100元" -v wallet="900元" -v file="2026-03-31-上海.md" '
  /^\| -/ {
    print
    print "| " date " | " city " | " price " | " wallet " | [查看](./" file ") |"
    next
  }
  /\| <br \/>/ { next }
  { print }
' /Users/hymanhai/TabiClaw/data/journals/index.md
