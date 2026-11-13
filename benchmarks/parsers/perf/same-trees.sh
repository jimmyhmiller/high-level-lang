#!/bin/bash
# Same printed tree (or same error) from two parser binaries for every file of a list.
A=$1; B=$2; L=$3; n=0; bad=0
while read f; do n=$((n+1)); a=$(out/bin/$A print "$f" 2>&1 | grep -v "0x0000" | shasum); b=$(out/bin/$B print "$f" 2>&1 | grep -v "0x0000" | shasum); [ "$a" != "$b" ] && { bad=$((bad+1)); echo "DIFF $f"; }; done < $L
echo "checked $n differ $bad"
