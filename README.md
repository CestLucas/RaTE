# RaTE
RaTE: a Reproducible automatic Taxonomy Evaluation by Filling the Gap (Code)

(Temporary) link to the paper: https://shorturl.at/hoDNU

**Minimalistic run:**  
*python rate.py -t "taxos/HiExpan1.txt"*

**Or with more specifications:**  
*python rate.py -t "taxos/HiExpan1.txt" -m "m1a" -k 10*

**Sample output:**  
Taxonomy path: taxos/HiExpan1.txt  
Pattern path: custom_queries/default_queries.txt  
Evaluation model: bert_base  
Number of predictions per query: 10  
RaTE score: 0.4961832061068702

**Required libraries:**  
torch  
transformers  
nltk  
pandas  
tqdm*  

Download the Yelp dataset used in the paper and code: https://shorturl.at/auvxT

Rest assured, more updates are coming soon!
