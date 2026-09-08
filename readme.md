cd ocudu_parent/inspector

#Installation

`sudo apt install python3.10-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt`



#Running

`sudo -v
 sudo docker logs --follow --since 0s open5gs_5gc 2>&1 \
  | python3 app.py --stdin --year 2026`
