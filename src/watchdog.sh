#!/bin/bash
# Restart any stopped step (e.g. after a quota stop) every 10 min until all calls are done.
cd "$(dirname "$0")"
count() { [ -f "$1" ] && python3 -c "import json,sys;print(len({json.loads(l)['call_id'] for l in open('$1') if json.loads(l).get('status')=='ok'}))" || echo 0; }
while true; do
  a=$(count ../calls/generation_evaluated_1.jsonl); b=$(count ../calls/generation_evaluated_2.jsonl)
  j=$([ -f ../out/judge_generation.jsonl ] && wc -l < ../out/judge_generation.jsonl || echo 0)
  echo "$(date +%H:%M) e1=$a e2=$b judged=$j"
  [ "$a" -ge 160 ] && [ "$b" -ge 160 ] && [ "$j" -ge 320 ] && echo ALL DONE && exit 0
  [ "$a" -lt 160 ] && ! pgrep -f "generate.py evaluated_1" >/dev/null && python3 generate.py evaluated_1 >> ../out/run_gen_e1.log 2>&1 &
  [ "$b" -lt 160 ] && ! pgrep -f "generate.py evaluated_2" >/dev/null && python3 generate.py evaluated_2 >> ../out/run_gen_e2.log 2>&1 &
  ! pgrep -f "judge.py" >/dev/null && python3 judge.py generation --follow >> ../out/run_judge_gen.log 2>&1 &
  sleep 600
done
