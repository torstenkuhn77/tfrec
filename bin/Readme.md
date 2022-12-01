Command Line für LaCrosse und TFA Sensoren

./tfrec -T 7 -g 48 -W -e "python pushtoinflux.py"

Im /bin Verzeichnis sind tfrec, influxdb.conf und pushtoinflux.py vorhanden

tfrec ruft das  Python Script mit folgenden Argumenten auf:

# id=$1
# temp=$2
# hum=$3
# seq=$4
# lowbatt=$5
# rssi=$6
# ts=$7
