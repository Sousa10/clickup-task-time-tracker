#!/usr/bin/env python
# coding: utf-8

# In[1]:


import requests
import pandas as pd
import time
import json
import pyodbc
import datetime


# # Function to insert in DB

# # Get Task from ClickUP

# In[2]:


AllTaskID = []


# In[3]:


cnxn = pyodbc.connect(driver="{SQL Server};server=WS001018;database=PIG;uid=sa;pwd=Pa$$w0rd;Trusted_Connection=yes;")
cursor = cnxn.cursor()


# In[4]:


def insert_data(data):
    # Create connection

    for i in data['tasks']:
        
        
        TaskID = i['id']
        AllTaskID.append(TaskID)
        
        TaskID
        
        #print("Task id: ",TaskID)
        TName  = i['name']
        TextContent  = i['text_content']
        TDescription  = i['description']
        DateCreated  = i['date_created']
        DateUpdated = int(i['date_updated'])
        DateClosed  = i['date_closed']
        DateDone  = i['date_done']
        Archived = i['archived']
        
        if Archived == "false":
            arch = 1
        else:
            arch = 0

        creatorDic = i['creator']
        CreatorName = creatorDic['username']
        CreatorEmail = creatorDic['email']


        Tags = i['tags']
        ParentID = i['parent']
        DueDate = i['due_date']
        StartDate = i['start_date']
        Points = i['points']
        TimeEstimate = i['time_estimate']
        Dependencies = i['dependencies']
        LinkedTasks = i['linked_tasks']
        TUrl = i['url']
        
        #print("ERRO")
        List = i['list']
        Listid = List['id']
        ListName = List['name']
        #print("Lista:", ListName,"TaskID:",TaskID) 

        LTTriority = i['priority']

        if not (LTTriority is None):
            TTriority = LTTriority['priority']
        else:
            TTriority = LTTriority
        
        query = """EXEC [dbo].[inserTaksCU] @TaskID = ? , @TName = ?, @TextContent = ?, 
                 @TDescription = ?, @DateCreated = ?, @DateClosed = ?, @DateDone = ?, @Archived = ?, @CreatorName = ?, 
                @CreatorEmail = ?, @Tags = ?, @ParentID = ? , @DueDate = ?, @StartDate = ?, @Points = ?,
                @TimeEstimate = ?, @Dependencies = ?, @LinkedTasks = ?, @TUrl = ?, @Listid = ?, @ListName = ?, 
                @TTriority = ?, @DateUpdated = ?"""

        

        value = (TaskID,TName, TextContent,TDescription,DateCreated,DateClosed, DateDone,arch,CreatorName,CreatorEmail,
                 str(Tags),ParentID,DueDate,StartDate,Points,TimeEstimate,str(Dependencies),str(LinkedTasks),TUrl,Listid,ListName,
                  TTriority, DateUpdated)
        
        
        cursor.execute(query,value)
        
        
        #checklist
        Checklists = i['checklists']


        if len(Checklists) > 0:
            cjDIC = Checklists[0]        
            for c in cjDIC['items']:
                cid = c['id']
                cname = c['name']
                cassi = str(c['assignee'])
                cGroupAssignee = str(c['group_assignee'])
                if c['resolved'] == 'true':
                    cresolved = 1
                else:
                    cresolved = 0
                ParentIDCK = c['parent']
                DateCreated = c['date_created']
                cChildren = str(c['children'])


                query2 = 'EXEC [dbo].[inserTaksCUCL] ? , ?, ?,?,?,?,?,?,?'
                value2 = (TaskID,cid,cname,cassi,cGroupAssignee,cresolved,ParentIDCK,DateCreated, cChildren)
                cursor.execute(query2,value2)
        
      
            
        #Status
        Status = (i['status'])['status']
        query3 = 'EXEC [dbo].[inserTaksStatus] ?,?,?'
        value3 = (TaskID,Status,DateUpdated)
        cursor.execute(query3,value3)

        #print("STATUS")

        #Time Track
        
        if "time_spent" in i:
            timeSpend = i['time_spent']
            query4 = 'EXEC [dbo].[inserTaksTimeTrack] ?,?,?'
            value4 = (TaskID,timeSpend,DateUpdated)
            cursor.execute(query4,value4)


        #Assigment

        query5 = "SELECT [username],[email]  FROM [PIG].[dbo].[TaskClickUpAssign] where TaskID = '"+TaskID+"'"
        cursor.execute(query5)
        assDB = pd.DataFrame.from_records(cursor.fetchall(),columns=[desc[0] for desc in cursor.description])


        #results = cursor.execute(query5).fetchall()
        #df = pd.read_sql(query, con)
        #assDB = pd.read_sql(query5,cnxn)

        #print('assDB')
        #print(assDB)
        allAssigm=[]
        allAssigm = i['assignees']
        aaReal = []
        for a in allAssigm:      
            #for c in assCP['items']:
            #print(a)
            nAss = a['username']
            emailAss = a['email']
            aaReal.append(emailAss)
            if emailAss not in assDB['email'].values or assDB.empty:
                query6 = """INSERT INTO [dbo].[TaskClickUpAssign] (
                                [TaskID]
                               ,[username]
                               ,[email])
                         VALUES
                               (?,?,?)"""
                value6 = (TaskID,nAss,emailAss)
                cursor.execute(query6,value6)
        now = datetime.datetime.now()
        nowBD = now.strftime("%Y/%m/%d")
        aaRealS = pd.Series(aaReal)

        for bd in assDB['email'].values:
            if bd not in aaRealS.values or aaRealS.empty:
                query7= """UPDATE [dbo].[TaskClickUpAssign]
                           SET [DataRemove] = ?
                             WHERE TaskID = ?
                             and email = ?; commit;"""
                value7 = (nowBD,TaskID,bd)
                cursor.execute(query7,value7)


# In[5]:


#import list of "list"
listsCU = pd.read_excel("Q:\\DSI\\Equipa\\PIG\\2026\\IniciativasPIGPlano_2026.xlsx", sheet_name="ListaClickUP")
terco = int(listsCU.shape[0]/3)
total = listsCU.shape[0]
listaID = listsCU['id']
#listaID
#print(listaID)


# In[6]:


#Import task from ClickUP
for x in range(terco+1): 
    id = str(listaID[x])
    str(int(listaID[x]))
    #print(id)
    
    url = "https://api.clickup.com/api/v2/list/" + id + "/task"
        
    query = {
      #"archived": "true",
      #"page": "0",
      #"order_by": "string",
      #"reverse": "true",
      "subtasks": "true",
      #"statuses": "string",
      "include_closed": "true"
      #"assignees": "string",
      #"tags": "string",
      #"due_date_gt": "0",
      #"due_date_lt": "0",
      #"date_created_gt": "0",
      #"date_created_lt": "0",
      #"date_updated_gt": "0",
      #"date_updated_lt": "0",
      #"date_done_gt": "0",
      #"date_done_lt": "0",
      #"custom_fields": "string"
    }

    headers = {
      "Content-Type": "application/json",
      "Authorization": "pk_49320107_ONLBQQTQ1O0WJSCOKPPADN5PAY0SNNXC"
    }

        
    response = requests.get(url, headers=headers, params=query)
    #print(url)
    
    data = response.json()


    #print(data)
    insert_data(data)


# In[7]:


time.sleep(90)


# In[8]:


for x in range(terco+1, terco*2):
    
    id = str(listaID[x])
    #print(id)
    url = "https://api.clickup.com/api/v2/list/" + id + "/task"
    #print(url)
    query = {
     #"archived": "true",
      #"page": "0",
      #"order_by": "string",
      #"reverse": "true",
      "subtasks": "true",
      #"statuses": "string",
      "include_closed": "true"
      #"assignees": "string",
      #"tags": "string",
      #"due_date_gt": "0",
      #"due_date_lt": "0",
      #"date_created_gt": "0",
      #"date_created_lt": "0",
      #"date_updated_gt": "0",
      #"date_updated_lt": "0",
      #"date_done_gt": "0",
      #"date_done_lt": "0",
      #"custom_fields": "string"
    }


    headers = {
      "Content-Type": "application/json",
      "Authorization": "pk_49320107_ONLBQQTQ1O0WJSCOKPPADN5PAY0SNNXC"
    }

    response = requests.get(url, headers=headers, params=query)

    data = response.json()
    #print(data)
    insert_data(data)


# In[9]:


time.sleep(90)


# In[10]:


print(listaID)


# In[11]:


for x in range((terco*2), total):
    
    id = str(listaID[x])
    #print(id)
    url = "https://api.clickup.com/api/v2/list/" + id + "/task"
    
    query = {
     #"archived": "true",
      #"page": "0", 
      #"order_by": "string",
      #"reverse": "true",
      "subtasks": "true",
      #"statuses": "string",
      "include_closed": "true"
      #"assignees": "string",
      #"tags": "string",
      #"due_date_gt": "0",
      #"due_date_lt": "0",
      #"date_created_gt": "0",
      #"date_created_lt": "0",
      #"date_updated_gt": "0",
      #"date_updated_lt": "0",
      #"date_done_gt": "0",
      #"date_done_lt": "0",
      #"custom_fields": "string"
    }


    headers = {
      "Content-Type": "application/json",
      "Authorization": "pk_49320107_ONLBQQTQ1O0WJSCOKPPADN5PAY0SNNXC"
    }

    response = requests.get(url, headers=headers, params=query)

    data = response.json()
    insert_data(data)


# In[12]:


#Delete task doesn't existe in DB
TaksExistCU = pd.DataFrame (AllTaskID, columns = ['TaskID'])
#print(TaksExistCU)
query9 = "SELECT TaskID FROM [PIG].[dbo].[TaskClickUp] where archive is null"
cursor.execute(query9)
tasksBD = pd.DataFrame.from_records(cursor.fetchall(),columns=[desc[0] for desc in cursor.description])
TaskDeleteBD = tasksBD[~ tasksBD["TaskID"].isin(TaksExistCU["TaskID"])]
#print(TaskDeleteBD)
for d in TaskDeleteBD["TaskID"]:
    #print(d)
    queryA = 'EXEC [dbo].[deleteTaskNotExist] ?'
    valueA = (d)
    cursor.execute(queryA,valueA)
queryA = 'EXEC [dbo].[deleteTaksCUCL]'
cursor.execute(queryA)


# In[13]:


#Agreggate time
query10 = "EXEC [dbo].[aggTimeUpdate];"
cursor.execute(query10)


# In[14]:


cursor.close()
cnxn.close()


# In[ ]:




