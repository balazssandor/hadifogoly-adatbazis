#!/bin/bash

declare -A darab=()
declare -A fele=()

FILE=$1

if [ $# -eq 3 ]
then
    COLS=$3
else
    COLS="2-4,6-9,13-16"
    # kimarad:
    #    1 sorszám
    #    5 szül év
    #   10 másodlagos település
    #   11 utca
    #   12 házszám
    #   17 másodlagos település
    #   18 utca
    #   19 házszám
    #   20 az mindig 'magyar'
fi

TMPFILE=$(mktemp)
TMPFILE_NO=$TMPFILE.NO
TMPFILE_YES=$TMPFILE.YES

POSITIVE_PTN="/"

for yesno in NO YES
do
    if [ $yesno == "NO" ] ;
    then
        SWITCH="-v"
    else
        SWITCH=""
    fi

cat $FILE | cut -d '	' -f $COLS | tr '+' ' ' | tr '	' '\n' | tr ' ' '\n' | grep -v "^$" | grep -v "^[0-9][0-9]*$" | grep $SWITCH $POSITIVE_PTN > $TMPFILE.$yesno
    
    darab[$yesno]=$(cat $TMPFILE.$yesno | wc -l)
    fele[$yesno]=$(cat $TMPFILE.$yesno | grep $SWITCH $POSITIVE_PTN | sort | uniq -c | sort -nr | wc -l)
done

ossz_darab=$((${darab[NO]} + ${darab[YES]}))
ossz_fele=$((${fele[NO]} + ${fele[YES]}))

for yesno in NO YES
do
    if [ $yesno == "NO" ] ;
    then
        SWITCH="-v"
    else
        SWITCH=""
    fi
 
    (
        darab_ezrelek=$((${darab[$yesno]} * 1000 / $ossz_darab))
        fele_ezrelek=$((${fele[$yesno]} * 1000 / $ossz_fele))

        darab_szazalek=$(echo $darab_ezrelek | sed "s/\(.\)$/.\1/")
        fele_szazalek=$(echo $fele_ezrelek | sed "s/\(.\)$/.\1/")

        echo "$yesno/darab:  ${darab[$yesno]}"
        if [ $yesno == "YES" ]
        then
            echo "$yesno/darab%: $darab_szazalek"
        fi
        echo "$yesno/féle:   ${fele[$yesno]}"
        if [ $yesno == "YES" ]
        then
            echo "$yesno/féle%:  $fele_szazalek"
        fi
        cat $TMPFILE.$yesno | grep $SWITCH "/" | sort | uniq -c | sort -nr | cat -n
    ) | less
done    

rm -f $TMPFILE
rm -f $TMPFILE_NO
rm -f $TMPFILE_YES

