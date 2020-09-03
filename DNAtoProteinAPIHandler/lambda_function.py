import boto3
import json
import uuid
import datetime
from boto3.dynamodb.conditions import Key, Attr


#lambda handler that is called when invoked by API Gateway Trigger, gets the 
#HTTP method and calls the appropriate function

def lambda_handler(event, context):
    
    httpMethod = event['context']['http-method']
    
    response = {'statusCode': 400, 'body': 'Unauthorized action'}
    
    if (httpMethod == "POST"):
        response = postData(event)
    elif (httpMethod == "GET"):
        response = getData(event)

    return response
    
    
#function that is called on an HTTP POST event, gets the appopriate values from
#the event and then inserts it into DynamoDB, and then calls the next function
#to insert it into SQS
def postData(event):
    httpBody = event['body-json']
    userIp = event['context']['source-ip']

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('DNAtoProtein')
    
    UUID = uuid.uuid1()
    current = datetime.datetime.today()
    formattedTime = '{:%m/%d/%y %I:%M:%S %p}'.format(current)
    seq = httpBody[4:].upper()
    
    response = table.put_item(
        Item={
            'userIP': userIp,
            'id': UUID.hex,
            'seq': seq,
            'TS': formattedTime,
            'mat': "",
            'stat': "NEW",
        }
    )
    
    #delivering the appropriate response to the client, and if everything is
    #ok, then we call sendToQueue()
    
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        response2 = sendToQueue(userIp, UUID.hex, seq, formattedTime)
        
        if response2['ResponseMetadata']['HTTPStatusCode'] == 200:
            return{
                'statusCode': 200,
                'body': UUID.hex
            }
        else:
            if (response2):
                return {
                    'statusCode': response2['ResponseMetadata']['HTTPStatusCode'],
                    'body': response2,
                    'update': "Something went wrong with !"
                }
            else:
                return {
                    'statusCode': 500,
                    'body': "We didn't get a response from SQS!"
                }
        
    else:
        if (response):
            return {
                'statusCode': response['ResponseMetadata']['HTTPStatusCode'],
                'body': response,
                'update': "Something went wrong with Dynamo!"
            }
        else:
            return {
                'statusCode': 500,
                'body': "We didn't get a response from Dynamo!"
            }
    
    
#function called on HTTP GET event, gets the appropriate values from table based
#on primary partition key userIP
def getData(event):
    userIp = event['context']['source-ip']
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('DNAtoProtein')
    
    response = table.query(
        KeyConditionExpression=Key('userIP').eq(userIp)
    )
    
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        items = response['Items']
        
        return{
            'statusCode': 200,
            'body': items
        }
    else:
        if (response):
            return {
                'statusCode': response['ResponseMetadata']['HTTPStatusCode'],
                'body': response,
                'update': "Something went wrong!"
            }
        else:
            return {
                'statusCode': 500,
                'body': "We didn't get a response from Dynamo!"
            }

#function called when a resquest is successfully inserted into DynamoDB, and
#then needs to get processed by another lambda via SQS
def sendToQueue(userIp, UUID, seq, TS):
    sqs = boto3.client('sqs')
    queue_url = 'https://sqs.us-east-2.amazonaws.com/956452502284/DNAtoProteinQueue'
    
    payload = {
        'userIP': userIp,
        'id': UUID,
        'seq': seq,
        'TS': TS,
        'stat': "NEW"
    }
    
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(payload)
    )
    
    return (response)
    
    