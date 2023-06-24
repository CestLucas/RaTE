# change the name to rate.py
import argparse
# from transformers import BertTokenizer, BertForMaskedLM, DistilBertForMaskedLM
from transformers import BertTokenizer, BertForMaskedLM
from transformers import pipeline
import nltk
# nltk.download('wordnet') // required for lemmatizer
# nltk.download('omw-1.4') // required for lemmatizer
from nltk.stem import WordNetLemmatizer
import torch
import pandas as pd
from tqdm import tqdm

from transformers import logging
logging.set_verbosity_error()

parser = argparse.ArgumentParser(description="RaTE: a Reproducible automatic Taxonomy Evaluation by Filling the Gap")
parser.add_argument('-t', '--taxo', help='Path to taxo in the format of concept pair.',
                    required=True)
parser.add_argument('-p', '--pattern', help='Path to the prompt patterns.',
                    default="custom_queries/default_queries.txt", required= False)
parser.add_argument('-m', '--model',
                    help='Select from m1a, m1b, m2a, m2b, m0a, m0b, bert_base or bert_large, default bert base. ',
                    default='bert_base', required=False)  # default is bert_base
parser.add_argument('-k', '--top_k',
                    help='Number of predictions generated by LLM per query.',
                    default=10, required=False)  # default is bert_base
parser.add_argument('-a', '--alternative',
                    help='Alternatively accepted predictions, e.g. "desert" for "dessert".',
                    default="results/acceptable_alternative_answers.txt",
                    required=False)  # default is bert_base

args = parser.parse_args()

query_templates = []
column_names = []
with open(args.pattern, "r") as fin:
    for line in fin.readlines():
        if not line.startswith("#"):
            query, name = line.split(",")
            query_templates.append(query.strip())
            column_names.append(name.strip())


eval_parents = []
eval_children = []
with open(args.taxo, "r") as fin:
    for concept_pair in fin.readlines():
        parent, child = concept_pair.split(',')
        eval_parents.append(parent.strip())
        eval_children.append(child.strip())

alt_accepted_answers = {}

with open(args.alternative, "r") as fin:
    for line in fin.readlines():
        taxo_ent, alts = line.split(":")
        taxo_ent = taxo_ent.strip()
        alt_ents = [x.strip() for x in alts.split(",")] + [taxo_ent]
        for ent in alt_ents:
            alt_accepted_answers[ent] = [x for x in alt_ents if x != ent]

# instantiate a standard bert-base tokenizer
bert_base_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
# instantiate another tokenizer for adding customized tokens
bert_base_extended = BertTokenizer.from_pretrained('bert-base-uncased')

not_in_bert_parent_lemmas = []

with open("../../DataspellProjects/RaTE (local)/model_configuration/add_tokenizer_vocabulary.txt", "r") as fin:
    for word in fin.readlines():
        not_in_bert_parent_lemmas.append(word.strip())

bert_base_extended.add_tokens(not_in_bert_parent_lemmas)

# can also use mps on mac
if torch.cuda.is_available():
    print("Using CUDA backend.")
    device = torch.device('cuda')
elif torch.backends.mps.is_available() and torch.backends.mps.is_built():
    print("Using MPS backend.")
    device = torch.device('mps')
else:
    print("Calculating using CPU.")
    device = torch.device('cpu')


if args.model in ['m1a', 'm1b', 'm2a', 'm2b', 'm0a', 'm0b']:
    model_path = "RaTE-Paper/yelp-" + parser.model
    tokenizer = bert_base_extended if parser.model in ['m1a', 'm1b', 'm2a', 'm2b'] else 'bert-base-uncased'
    unmasker = pipeline('fill-mask', tokenizer=tokenizer, model=model_path, device=device)
elif args.model == 'bert_large':
    unmasker = pipeline('fill-mask', model='bert-large-uncased-whole-word-masking', device=device)
else:
    unmasker = pipeline('fill-mask', model='bert-base-uncased', device=device)

lemmatizer = WordNetLemmatizer()


def lemmatize_a_word(word):
    split_word = word.split()
    # print(split_word)
    ngram=len(split_word)
    if ngram == 1:
        return lemmatizer.lemmatize(word, pos='n')
    else:
        last_word =split_word[-1]
        lem = lemmatizer.lemmatize(last_word, pos='n')
        new_word = ' '.join(split_word[:-1] + [lem])
        return new_word


def generate_queries_from_template(token):
    test_queries = []

    for template in query_templates:
        test_queries.append(template.replace("{token}", token) + " .")

    return test_queries


predictions = {}

# get 1e results
print("Calculating score...")
for child in tqdm(eval_children):
    queries = generate_queries_from_template(child)
    # queries = generate_queries_paper(child)
    queries_unmasked = unmasker(queries, top_k=args.top_k)
    for i, column in enumerate(column_names):
        if child not in predictions:
            predictions[child] = {}
        predictions[child][column] = queries_unmasked[i]


def generate_result_frame(accept_noisy_answers=False):
    df_result = pd.DataFrame()
    df_result["hypernym"] = eval_parents
    df_result["hyponym"] = eval_children

    for column_name in column_names:
        query_predictions = []

        for parent, child in zip(eval_parents, eval_children):
            preds = predictions[child][column_name]

            parent_in_preds = False

            for pred_list in preds:
                if parent == pred_list['token_str']:
                    parent_in_preds = True
                    break
                if accept_noisy_answers:
                    if parent in alt_accepted_answers:
                        if pred_list['token_str'] in alt_accepted_answers[parent]:
                            parent_in_preds = True
                            break
            query_predictions.append(parent_in_preds * 1)

        df_result[column_name] = query_predictions

    df_result['sum'] = df_result[column_names].sum(axis=1)
    return df_result


df_result = generate_result_frame(accept_noisy_answers=True)

print("Taxonomy path:", args.taxo)
print("Pattern path:", args.pattern)
print("Evaluation model:", args.model)
print("Number of predictions per query:", args.top_k)
print("RaTE score:", len(df_result.loc[df_result["sum"] > 0]) / len(df_result))