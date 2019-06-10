import requests
import datetime
import xmltodict
import os
import json
import uuid
import xlsxwriter
import openpyxl
from bottle import abort, request, static_file, run, route

temp_path = os.path.dirname(os.path.abspath(__file__)) + os.path.sep + "tmp"
if not os.path.exists(temp_path):
    os.makedirs(temp_path)

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={}[Author]"
PUBMED_DATE_QUERY = '+AND+("{}"[PDat] : "{}"[PDat])'
PUBMED_DOWNLOAD_CSV =  "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={}&rettype=fasta&retmode=xml"
#Date_format:YYYY/MM/DD
headers = ["GM Universal Code", "Full Name", "Author Match","Title","URL", "Query Used","Description","Details","ShortDetails", "Affiliation","Resource","Type","Identifiers","Db","EntrezUID","Properties"]



def create_xlsx(data):
    file_name = str(uuid.uuid4())+".xlsx"
    workbook = xlsxwriter.Workbook(temp_path + os.path.sep + file_name)
    worksheet = workbook.add_worksheet()
    row = 0
    col = 0
    for header in headers:
        worksheet.write(row, col, header)
        col += 1
    
    for col_data in data:
        row += 1
        col = 0
        for header in headers:
            #print("header--> {}:data-->{}:type--->{}".format(header,col_data[header],type(col_data[header])))
            worksheet.write(row, col, col_data[header])
            col += 1

    workbook.close()        
    return file_name

def xml_to_json(xml):
    ''' This API converts xml data to json
        parameters:
        ---------------
        xml (str) : Complete xml data read from website or file

        return:
        ---------------
        json(dict) : returns valid dictionary
    '''
    json_string = json.dumps(xmltodict.parse(xml))
    json_data = json.loads(json_string)
    return json.dumps(json_data)

def get_description(auther_list):
    desc = ""
    i = 0
    if type(auther_list) == dict:
        auther_list = [auther_list]
    for author in auther_list:
        i += 1
        if author.get("CollectiveName",None):
            desc += author["CollectiveName"]
        else:
            desc += author["LastName"] + " " + author.get("Initials","")
        if len(auther_list) == i:
            desc += "."
        else:
            desc += ", "
    return desc 

def get_affiliation_details(auther_name, auther_list):
    if type(auther_list) == dict:
        auther_list = [auther_list]
    name_list = auther_name.replace(",","").lower().split(" ")
    for author in auther_list:
        if author.get("AffiliationInfo"):
            if type(author["AffiliationInfo"]) == dict:
                author["AffiliationInfo"] = [author["AffiliationInfo"]]
                data = ""
                i = 0
                if author.get("LastName", "").lower() in name_list or author.get("ForeName", "").lower() in name_list:
                    for aff_info in author["AffiliationInfo"]:
                        data += aff_info["Affiliation"]
                        i = i+ 1
                        if len(author["AffiliationInfo"]) != i:
                            data += ", "
                        else:
                            data += "."
 
                    return data
    return ""

def get_journal_issue_details(journal_issue):
    data = "{} {} {};".format(journal_issue["PubDate"].get("Year",""), journal_issue["PubDate"].get("Month",""),journal_issue["PubDate"].get("Day",""))
    if journal_issue.get("Volume"):
        data += " {}({}).".format(journal_issue["Volume"],journal_issue.get("Issue",0)) 
    return data

def get_elocation_details(elocationid):
    if type(elocationid) == dict:
        elocationid = [elocationid]
    data = ""
    for value in elocationid:
        data += "{}: {}. ".format(value["@EIdType"],value["#text"])
    return data

def get_details(journal, elocationid):
    data = "{}. {} {}".format(journal["ISOAbbreviation"],get_journal_issue_details(journal["JournalIssue"]),get_elocation_details(elocationid))
    return data

def get_short_details(journal):
    data = "{}. {}".format(journal["ISOAbbreviation"], journal["JournalIssue"]["PubDate"].get("Year",""))
    return data

def get_create_date(pub_dates):
    for date in pub_dates:
        if date["@PubStatus"] in ["pubmed", "medline"]:
            data = "{}/{}/{}".format(date.get("Year",""), date["Month"], date["Day"])
            return data
    return ""
    
def get_first_author(auther_list):
    if type(auther_list) == dict:
        auther_list = [auther_list]
    data = ""
    for author in auther_list:
        try:
            data = author["LastName"] + " " + author.get("Initials","")
            return data
        except KeyError:
            if author.get("CollectiveName",None):
                data = author["CollectiveName"]
    return data    
        
def get_full_name(name, auther_list):
    if type(auther_list) == dict:
        auther_list = [auther_list]
    name_list = name.replace(",","").lower().split(" ")
    for author in auther_list:
        if author.get("LastName", "").lower() in name_list or author.get("ForeName", "").lower() in name_list:
            return author["LastName"] + ", " + author.get("ForeName","")
    return name

def get_properties(pub_dates,auther_list):
    data = "create date:{} | first author:{}".format(get_create_date(pub_dates), get_first_author(auther_list))
    return data 

@route('/upload', method='POST')
def do_upload():

    upload     = request.files.get('upload')
    name, ext = os.path.splitext(upload.filename)
    
    if ext in ('.png','.jpg','.jpeg'):
        return 'File extension not allowed.'

    upload.save(temp_path) # appends upload.filename automatically
    
    from_date = request.forms.get('from_date') if request.forms.get('from_date') else None
    to_date = request.forms.get('to_date') if request.forms.get('to_date') else None


    if from_date and to_date:
        if datetime.datetime.strptime(from_date, "%Y-%m-%d") > datetime.datetime.strptime(to_date, "%Y-%m-%d"):
            return '<html><script>alert("from date should be lesser than to date");</script><html>'

    try:
        xlsx_file_path = os.path.join(temp_path, upload.filename)
        xlsx_data = []
        wb_obj = openpyxl.load_workbook(xlsx_file_path)
        sheet_obj = wb_obj.active
        for i in range(1, sheet_obj.max_row+1):
            row_data = {}
            for j in range(1, sheet_obj.max_column+1):
                row_data[sheet_obj.cell(row = 1, column = j).value] = sheet_obj.cell(row = i+1, column = j).value
            xlsx_data.append(row_data)
        
        os.remove(xlsx_file_path)
        ids_return_data = {"ids_info":{},"count":0}

        for column_data in xlsx_data:
            name = column_data["Name"] if column_data.get("Name") else None
            uid = column_data["Uid"] if column_data.get("Uid") else None

            if name is not None:
                search_data = search_citations(name, universal_id=uid, local_searh=True, from_date=from_date, to_date=to_date)
                if search_data["count"] != 0:
                    ids_return_data["ids_info"].update(search_data["ids_info"])
                    ids_return_data["count"] += len(search_data["ids_info"].keys())
                    if ids_return_data["count"] >= 200:
                        break
        
        if ids_return_data["count"] != 0:
            file_path = download_csv(ids_return_data, local=True)

            return static_file(file_path, temp_path, download=file_path)
    except Exception as ex:
        print("Exception in upload:{}".format(ex))
        abort(500, "Exception occurred: {}".format(ex))        


@route("/search", method='POST')
def search_citations(name=None, universal_id=None,from_date=None, to_date=None,  records_per_page="100", local_searh=False):
    try:
        if not local_searh:
            name = request.forms.get('Name')  if request.forms.get('Name') else None
            records_per_page = request.forms.get('retmax') if request.forms.get('retmax') else "200"
            universal_id = request.forms.get('Uid') if request.forms.get('Uid') else str(uuid.uuid4())
            from_date = request.forms.get('from_date')  if request.forms.get('from_date') else None
            to_date = request.forms.get('to_date')  if request.forms.get('to_date') else None
        
        url = None
        search_name = "" + name
        if search_name:
            if "," not in search_name:
                if " " in search_name:
                    search_name = search_name.replace(" ", "+")
        
            url = PUBMED_SEARCH_URL.format(search_name)
        else:
            raise Exception("Name is madatory field")

        if from_date and to_date:
            if datetime.datetime.strptime(from_date, "%Y-%m-%d") > datetime.datetime.strptime(to_date, "%Y-%m-%d"):
                return '<html><script>alert("from date should be lesser than to date");</script><html>'

            url = url + PUBMED_DATE_QUERY.format(from_date,to_date)
        
        query_url = url.split("&term=")[-1]

        if not url:
            raise Exception("Unable to build search url")
        url += "&retmax={}".format(records_per_page)

        print("pubmed search url: {}".format(url))
        r = requests.get(url=url,headers= {"Content-Type": "application/xml","accept": "application/xml"})
        if r.status_code == 200:
            json_data = json.loads(xml_to_json(r.text))
        else:
            raise Exception("Error occured while comunicating with pubmed{}".format(r.status_code))
        
        if int(json_data["eSearchResult"]["Count"]) <= 0:
            return {"ids_info":{},"count":0 }

        id_list = json_data["eSearchResult"]["IdList"].get("Id",None)

        return_data = {"ids_info":{}}
        for _id in id_list:
            return_data["ids_info"][_id] = {"name": name,"query":query_url,"univeral_id":universal_id}

        return_data["count"] = len(return_data["ids_info"].keys())

        if return_data["count"] != 0:
            
            file_path = download_csv(return_data, local=True)
            print(file_path)

        if not local_searh:
            return static_file(file_path, temp_path, download=file_path)
        else:
            return return_data

    except Exception as ex:
        print("search_citations:Exception occurred: {}".format(ex))
        abort(500, "Exception occurred: {}".format(ex))


@route("/pubmed/download")
def download_csv(query_data=None, local=False):
    try:
        
        xlsx_data = []
        if not local:
            query_data = json.loads(request.query.data) if request.query.data else None
    
        if not query_data:
            raise Exception("query_data is madatory field")
        if not query_data.get("count") or not query_data.get("ids_info"):
            raise Exception("Invalid data provided")

        ids = ",".join(query_data["ids_info"].keys())

        url = PUBMED_DOWNLOAD_CSV.format(ids)
        print("pubmed download csv url: {}".format(url))
        r = requests.get(url=url,headers= {"Content-Type": "application/xml","accept": "application/xml"})
        if r.status_code == 200:
            json_data = json.loads(xml_to_json(r.text))
            if type(json_data["PubmedArticleSet"]["PubmedArticle"]) == dict:
                json_data["PubmedArticleSet"]["PubmedArticle"] = [json_data["PubmedArticleSet"]["PubmedArticle"]]
            
            for data in json_data["PubmedArticleSet"]["PubmedArticle"]:
                medline_data = data["MedlineCitation"]
                article_data = medline_data["Article"]
                publication_date = data["PubmedData"]
                form_data = {}
                if type(article_data["ArticleTitle"]) == dict:
                    form_data["Title"] = article_data["ArticleTitle"]["#text"]
                else:
                    form_data["Title"] = article_data["ArticleTitle"]
                form_data["URL"] = "https://www.ncbi.nlm.nih.gov/pubmed/" + medline_data["PMID"]["#text"]
                form_data["Description"] = get_description(article_data["AuthorList"]["Author"])
                if article_data.get("ELocationID"):
                    form_data["Details"] = get_details(article_data["Journal"], article_data["ELocationID"])
                else:
                    form_data["Details"] = "{}. {}".format(article_data["Journal"]["ISOAbbreviation"],get_journal_issue_details(article_data["Journal"]["JournalIssue"]))
                
                form_data["GM Universal Code"] = query_data["ids_info"][medline_data["PMID"]["#text"]]["univeral_id"]
                form_data["Affiliation"] = get_affiliation_details(query_data["ids_info"][medline_data["PMID"]["#text"]]["name"], article_data["AuthorList"]["Author"])
                form_data["Query Used"] = query_data["ids_info"][medline_data["PMID"]["#text"]]["query"]
                form_data["ShortDetails"] = get_short_details(article_data["Journal"])
                form_data["Resource"] = "PubMed"
                form_data["Type"] = "citation"
                form_data["Full Name"] = get_full_name(query_data["ids_info"][medline_data["PMID"]["#text"]]["name"], article_data["AuthorList"]["Author"])
                form_data["Identifiers"] = "PMID:" + medline_data["PMID"]["#text"]
                form_data["Db"] = "pubmed"
                form_data["EntrezUID"] = medline_data["PMID"]["#text"]
                form_data["Author Match"] = get_full_name(query_data["ids_info"][medline_data["PMID"]["#text"]]["name"], article_data["AuthorList"]["Author"])
                form_data["Properties"] = get_properties(publication_date["History"]["PubMedPubDate"], article_data["AuthorList"]["Author"])
                xlsx_data.append(form_data)
        else:
            raise Exception("Error occured while comunicating with pubmed, status_code({})".format(r.status_code))

        if not xlsx_data:
            raise Exception("Error occured while comunicating with pubmed")
        
        file_name = create_xlsx(xlsx_data)
        if local:
            return file_name
        return static_file(file_name, temp_path, download=file_name)
    except Exception as ex:
        print("download_csv:Exception occurred: {}".format(ex))
        abort(500, "Exception occurred: {}".format(ex))


@route("/css/<css_file>")
def serve_css(css_file):
    return static_file(css_file, os.path.dirname(os.path.abspath(__file__))+os.path.sep+"css")

@route("/")
def serve_web():
    return static_file("index.html", os.path.dirname(os.path.abspath(__file__)))

run(host="0.0.0.0",port=8090)
