import boto3
import json
import csv
import io
import json
import os
  
# Environment variables setting
region = os.environ['REGION_NAME']
bedrock_model_id = os.environ['BEDROCK_MODEL']
# email = os.environ['EMAIL_ADDRESS']
table_name = os.environ['NOTI_TABLE']
partition_key = os.environ['PARTITION_KEY']



# Initialize S3 & SNS & DynamoDB client
s3 = boto3.client('s3', region)
sns_client = boto3.client('sns')
dynamodb = boto3.resource('dynamodb') 


def save_to_dynamodb(message_id, subject, message):
    
    table = dynamodb.Table(table_name)
    
    # Define the item to be inserted
    item = {
        partition_key: message_id,
        'Subject': subject,
        'Message': message,
        # 'RecordTime': datetime.now()
    }
    
    # Insert the item into DynamoDB
    table.put_item(Item=item)
    
    print(f'Jobs {message_id} created successfully')


def lambda_handler(event, context):

    # 設定存儲桶名稱和檔案名稱
    # Extract information from the event
    for record in event['Records']:
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        event_name = record['eventName']
        
        # bucket_name = 'rong-test-0512'
        # file_key = 'energy.csv'
    
        # 讀取 CSV 檔案
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        csv_content = response['Body'].read().decode('utf-8')
        
        # 將 CSV 轉換為 JSON 格式
        csv_rows = csv.DictReader(io.StringIO(csv_content))
        json_output = json.dumps([row for row in csv_rows])
        print(json_output)
    
    # json_content2 = [
    #    {"date": "2024/3/4", "career": "102", "store": "10202", "net": "45237"}, {"date": "2024/3/5", "career": "102", "store": "10202", "net": "34786"}
    # ]
    
    # # 將 JSON 轉換為字串
    # json_output2 = json.dumps(json_content2)



        # 根據 CSV 檔案的內容動態生成提示訊息
    
        prompt = f'explain the text {json_output}'
        # prompt = f'explain the text {json_output2}'
            
        # 建立 Bedrock 客戶端
        bedrock = boto3.client(
            service_name='bedrock-runtime'#,
            # region_name='us-west-2'
        )  
    
        
        # 設置 Bedrock 模型的輸入參數
        input_data = {
            "modelId": bedrock_model_id,  # "cohere.command-text-v14",
            "contentType": "application/json",
            "accept": "*/*",
            "body": {
                "prompt": prompt,
                "max_tokens": 1000,
                "temperature": 0.75,
                "p": 0.01,
                "k": 0,
                "stop_sequences": [],
                "return_likelihoods": "NONE"
            }
        }
        
        # 呼叫 Bedrock 模型
        response = bedrock.invoke_model(
            body=json.dumps(input_data["body"]),
            modelId=input_data["modelId"],
            accept=input_data["accept"],
            contentType=input_data["contentType"]
        )
    
        # 讀取上面的s3內檔案並解析回應
        response_body = json.loads(response['body'].read())
        explanation = response_body['generations'][0]['text']
        # print(explanation)

        sns_topic_arn = os.environ['SNS_ARN']
        message_text = f"Dear Facility Manager, \n {explanation} \n Regards,\n Your AI Assistant"
        subject_text = "Facility update: Action required for anomalous data"
        try:
            sent_message = sns_client.publish(TopicArn=sns_topic_arn, Message=message_text, Subject=subject_text)
            if sent_message['ResponseMetadata']['HTTPStatusCode'] == 200:
                print(sent_message)
                print("Notification send successfully..!!!")
                #return True
                message_id = sent_message['MessageId']
                save_to_dynamodb(message_id, subject_text, message_text)
                print("Notification stored successfully..!!!")
        except Exception as e:
            print("Error occured while publish notifications and error is : ", e)
            return True
