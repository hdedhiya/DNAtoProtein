import json
import time
import random
import boto3
import Bio
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.Alphabet import IUPAC
import os
import os.path

#lambda handler that is called on an SQS event, with batch_size set to 1 so that
#each lambda only handles one request. Finds a match and then updates the table
#in DynamoDB
def lambda_handler(event, context):
    
    event_dict = json.loads(event['Records'][0]['body'])

    match = findMatch(event_dict['seq'])
    
    updateTable(event_dict['userIP'], event_dict['id'], match)
 
 
#function called to find a match of a sequence
#Gets the original and reverse_complement
#Gets list of 1000 objects in S3 Bucket, creates a random permutation
#Then iterates to find first match, and returns when match is found
def findMatch(inputSeq):

    formattedSeq = Seq(inputSeq, IUPAC.unambiguous_dna)
    revComplementSeq = formattedSeq.reverse_complement()

    client = boto3.client('s3')
    bucketname = 'dna-to-protein-bucket'
    
    genome_list = []
    
    response = client.list_objects(Bucket=bucketname)
    for item in response['Contents']:
        genome_list.append(item['Key'])
        
    sample = random.sample(genome_list, len(genome_list))
    
    s3 = boto3.resource('s3')
    
    for i in range(len(sample)):

        s3.meta.client.download_file(bucketname, sample[i], '/tmp/record.gb')
        record = SeqIO.read('/tmp/record.gb', 'genbank')
        
        index = record.seq.find(formattedSeq)
        rev_index = record.seq.find(revComplementSeq)
        
        if index != -1 or rev_index != -1:
            for feature in record.features:
                if feature.type == 'CDS':
                    if feature.location.start <= index and feature.location.end > index:
                        return feature.qualifiers.get('protein_id')[0]
                    elif feature.location.start <= rev_index and feature.location.end > rev_index:
                        return feature.qualifiers.get('protein_id')[0]
                        
    return "NO MATCH"
    
    
#function called when matching is done, updates status and match in DynamoDB
def updateTable(userIp, id, match):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('DNAtoProtein')
    
    response = table.update_item(
    Key={
        'userIP': userIp,
        'id': id
    },
    UpdateExpression='SET stat = :val1, mat = :val2',
    ExpressionAttributeValues={
        ':val1': 'COMPLETED',
        ':val2': match
    })
    
    