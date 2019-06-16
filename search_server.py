import requests
import datetime
import xmltodict
import os
import json
import uuid
import xlsxwriter
from multiprocessing import process
import openpyxl
from bottle import abort, request, static_file, run, route
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

temp_path = os.path.dirname(os.path.abspath(__file__)) + os.path.sep + "tmp"
if not os.path.exists(temp_path):
    os.makedirs(temp_path)

MY_API_KEY = "6f63b0b5ec41afd50bed862a0d61ff0ae709"
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&api_key=6f63b0b5ec41afd50bed862a0d61ff0ae709&term={}"
PUBMED_DATE_QUERY = '+AND+("{}"[PDat] : "{}"[PDat])'
#PUBMED_DOWNLOAD_CSV =  "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={}&rettype=fasta&retmode=xml&api_key=6f63b0b5ec41afd50bed862a0d61ff0ae709"
PUBMED_DOWNLOAD_CSV =  "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&rettype=fasta&retmode=xml&api_key=6f63b0b5ec41afd50bed862a0d61ff0ae709"
#Date_format:YYYY/MM/DD
headers = ["GM Universal Code", "Full Name", "Author Match","Authorship_Position", "Publication_Type", "Mesh_Headings","Title","URL", "Query Used",
          "Description","Details","ShortDetails", "Affiliation","Resource","Type","Identifiers","Db","EntrezUID","Properties", "Author_Count", "Abstract_Text"]



def create_xlsx(data=None, data_list=[], local=False):
    file_name = str(uuid.uuid4())+".xlsx"
    workbook = xlsxwriter.Workbook(temp_path + os.path.sep + file_name)
    worksheet = workbook.add_worksheet()
    row = 0
    col = 0
    for header in headers:
        worksheet.write(row, col, header)
        col += 1
    
    if not local:
        for col_data in data:
            row += 1
            col = 0
            for header in headers:
                #print("header--> {}:data-->{}:type--->{}".format(header,col_data[header],type(col_data[header])))
                worksheet.write(row, col, col_data[header])
                col += 1
    else:
        for data in data_list:
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
            if author.get("LastName", "") is None:
                author["LastName"] = ""
            if author.get("ForeName", "") is None:
                author["ForeName"] = ""
            if author.get("Initials", "") is None:
                author["Initials"] = ""
            desc += author.get("LastName","") + " " + author.get("Initials","")
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
                if author.get("LastName", "") is None:
                    author["LastName"] = ""
                if author.get("ForeName", "") is None:
                    author["ForeName"] = ""
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
    data = "{}. {} {}".format(journal.get("ISOAbbreviation",""),get_journal_issue_details(journal["JournalIssue"]),get_elocation_details(elocationid))
    return data

def get_short_details(journal):
    data = "{}. {}".format(journal.get("ISOAbbreviation", ""), journal["JournalIssue"]["PubDate"].get("Year",""))
    return data

def get_create_date(pub_dates):
    if type(pub_dates) == dict:
        pub_dates = [pub_dates]
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
            if author.get("LastName", "") is None:
                author["LastName"] = ""
            if author.get("ForeName", "") is None:
                author["ForeName"] = ""
            if author.get("Initials", "") is None:
                author["Initials"] = ""
            data = author.get("LastName","") + " " + author.get("Initials","")
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
        if author.get("LastName", "") is None:
            author["LastName"] = ""
        if author.get("ForeName", "") is None:
            author["ForeName"] = ""
        if author.get("LastName", "").lower() in name_list or author.get("ForeName", "").lower() in name_list:
            return author.get("LastName", "") + ", " + author.get("ForeName","")
    return name

def get_author_position(name, auther_list):
    if type(auther_list) == dict:
        auther_list = [auther_list]
    name_list = name.replace(",","").lower().split(" ")
    for author in auther_list:
        if author.get("LastName", "") is None:
            author["LastName"] = ""
        if author.get("ForeName", "") is None:
            author["ForeName"] = ""
        if author.get("LastName", ""):
            if author.get("LastName", "").lower() in name_list:
                if author.get("ForeName", ""):
                    forename = author.get("ForeName", "").split(" ")[0]
                    if forename.lower() in name_list:
                        return auther_list.index(author) + 1
                else:
                    return auther_list.index(author) + 1
    return 0


def get_publication_type(publication_type_list):
    data = []
    if type(publication_type_list) == dict:
        publication_type_list = [publication_type_list]
    for type_ in publication_type_list:
        data.append(type_["#text"])
    return ";".join(data)

def get_mesh_headings(mesh_heading_list):
    data = []
    if type(mesh_heading_list) == dict:
        mesh_heading_list = [mesh_heading_list]
    for heading in mesh_heading_list:
        if heading.get("DescriptorName",""):
            data.append(heading["DescriptorName"].get("#text",""))
    return ";".join(data)


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

        xlsx_data_list = []

        for column_data in xlsx_data:
            print("\n\n{} of {}\n\n".format(xlsx_data.index(column_data)+1, len(xlsx_data)))
            name = column_data["Full_Name"] if column_data.get("Full_Name") else None
            uid = column_data["KOL_ID"] if column_data.get("KOL_ID") else None
            firstname = column_data["First_Name"] if column_data.get("First_Name") else None
            initial = column_data["Middle_Name"] if column_data.get("Middle_Name") else None
            lastname = column_data["Last_Name"] if column_data.get("Last_Name") else None
            if name is not None:
                search_data = search_citations(name=name, initial=initial, lastname=lastname, firstname=firstname, universal_id=uid, local_searh=True, from_date=from_date, to_date=to_date, records_per_page=4000)
                if search_data["count"] != 0:
                    
                    ids_return_data["ids_info"].update(search_data["ids_info"])                
                    ids_return_data["count"] += len(search_data["ids_info"].keys())
                    xlsx_data_list.append(download_csv(search_data, local=True))

        if ids_return_data["count"] != 0:
            
            file_path = create_xlsx(data_list=xlsx_data_list, local=True)
            return static_file(file_path, temp_path, download=file_path)
    except Exception as ex:
        print("Exception in upload:{}".format(ex))
        abort(500, "Exception occurred: {}".format(ex))        


@route("/search", method='POST')
def search_citations(name=None, initial=None, lastname=None, firstname=None, universal_id=None,from_date=None, to_date=None,  records_per_page="400", local_searh=False):
    try:
        if not local_searh:
            name = request.forms.get('Name')  if request.forms.get('Name') else None
            records_per_page = request.forms.get('records') if request.forms.get('records') else "420"
            universal_id = request.forms.get('Uid') if request.forms.get('Uid') else str(uuid.uuid4())
            from_date = request.forms.get('from_date')  if request.forms.get('from_date') else None
            to_date = request.forms.get('to_date')  if request.forms.get('to_date') else None
            initial = request.forms.get('Initial')  if request.forms.get('Initial') else None
            lastname = request.forms.get('Lastname')  if request.forms.get('Lastname') else None
            firstname = request.forms.get("FirstName") if request.forms.get('FirstName') else None
        
        
        url = None
        if not name:
            raise Exception("Name is madatory field")

        search_name = "" + name + "[Full Author Name]"
        if search_name:
        
            if firstname and initial and lastname:
                search_name += "+OR+{}{} {}[Full Author Name]".format(firstname[0], initial[0],lastname)
                search_name += "+OR+{}, {}{}[Full Author Name]".format(lastname, firstname[0], initial[0])
                search_name += "+OR+{}, {} {}[Full Author Name]".format(lastname, firstname, initial)
                search_name += "+OR+{}, {} {}[Full Author Name]".format(lastname, firstname, initial[0])
                 
            if lastname and firstname:
                search_name += "+OR+{}, {}[Full Author Name]".format(lastname, firstname)
                search_name += "+OR+{} {}[Author]".format(firstname, lastname)
                search_name += "+OR+{}, {}[Full Author Name]".format(lastname, firstname[0])

            url = PUBMED_SEARCH_URL.format(search_name)

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

            if not local_searh:
                file_path = download_csv(query_data=return_data, local=local_searh)
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
        # if not local:
        #     query_data = json.loads(request.query.data) if request.query.data else None
    
        if not query_data:
            raise Exception("query_data is madatory field")
        if not query_data.get("count") or not query_data.get("ids_info"):
            raise Exception("Invalid data provided")

        ids = ",".join(query_data["ids_info"].keys())

        url = PUBMED_DOWNLOAD_CSV
        print("pubmed download csv url: {}".format(url))
        r = requests.post(url=url, data="id={}".format(ids),headers= {"accept": "application/xml"})
        if r.status_code == 200:
            json_data = json.loads(xml_to_json(r.text))
            if type(json_data["PubmedArticleSet"]["PubmedArticle"]) == dict:
                json_data["PubmedArticleSet"]["PubmedArticle"] = [json_data["PubmedArticleSet"]["PubmedArticle"]]
            
            for data in json_data["PubmedArticleSet"]["PubmedArticle"]:
                medline_data = data["MedlineCitation"]
                article_data = medline_data["Article"]
                publication_date = data["PubmedData"]
                mesh_heading_data = medline_data.get("MeshHeadingList",{})
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
                    
                    form_data["Details"] = "{}. {}".format(article_data["Journal"].get("ISOAbbreviation",""),get_journal_issue_details(article_data["Journal"]["JournalIssue"]))

                form_data["GM Universal Code"] = query_data["ids_info"][medline_data["PMID"]["#text"]]["univeral_id"]
                form_data["Affiliation"] = get_affiliation_details(query_data["ids_info"][medline_data["PMID"]["#text"]]["name"], article_data["AuthorList"]["Author"])
                form_data["Query Used"] = query_data["ids_info"][medline_data["PMID"]["#text"]]["query"]
                form_data["ShortDetails"] = get_short_details(article_data["Journal"])
                form_data["Resource"] = "PubMed"
                form_data["Type"] = "citation"
                form_data["Full Name"] =   query_data["ids_info"][medline_data["PMID"]["#text"]]["name"]    #get_full_name(query_data["ids_info"][medline_data["PMID"]["#text"]]["name"], article_data["AuthorList"]["Author"])
                form_data["Identifiers"] = "PMID:" + medline_data["PMID"]["#text"]
                form_data["Db"] = "pubmed"
                if article_data.get("PublicationTypeList"):
                    form_data["Publication_Type"] = get_publication_type(article_data["PublicationTypeList"].get("PublicationType",[]))
                else:
                    form_data["Publication_Type"] = ""
                
                if mesh_heading_data.get("MeshHeading"):
                    form_data["Mesh_Headings"] = get_mesh_headings(mesh_heading_data.get("MeshHeading",[]))
                else:
                    form_data["Mesh_Headings"] = ""
                
                form_data["Authorship_Position"] = get_author_position(query_data["ids_info"][medline_data["PMID"]["#text"]]["name"], article_data["AuthorList"]["Author"])
                form_data["Author_Count"] = len(article_data["AuthorList"]["Author"])
                form_data["Abstract_Text"] = ""
                if article_data.get("Abstract",None):
                    if article_data["Abstract"].get("AbstractText",""):
                        if type(article_data["Abstract"]["AbstractText"]) == list:
                            for text in article_data["Abstract"]["AbstractText"]:
                                if text:
                                    if type(text) == dict:
                                        form_data["Abstract_Text"] += text.get("#text","")
                                    else:
                                        form_data["Abstract_Text"] += text   
                                form_data["Abstract_Text"] += ";"

                        elif type(article_data["Abstract"]["AbstractText"]) == dict:
                            form_data["Abstract_Text"] = article_data["Abstract"]["AbstractText"].get("#text")
                        else:
                            form_data["Abstract_Text"] = article_data["Abstract"]["AbstractText"]

                form_data["EntrezUID"] = medline_data["PMID"]["#text"]
                form_data["Author Match"] = get_full_name(query_data["ids_info"][medline_data["PMID"]["#text"]]["name"], article_data["AuthorList"]["Author"])
                form_data["Properties"] = get_properties(publication_date["History"]["PubMedPubDate"], article_data["AuthorList"]["Author"])
                xlsx_data.append(form_data)
        else:
            raise Exception("Error occured while comunicating with pubmed, status_code({}),text({})".format(r.status_code,r.text))

        if not xlsx_data:
            raise Exception("Error occured while comunicating with pubmed")
        
        if local:
            return xlsx_data

        file_name = create_xlsx(data=xlsx_data, local=False)

        return file_name
    except Exception as ex:
        print("download_csv:Exception occurred: {}".format(ex))
        abort(500, "Exception occurred: {}".format(ex))


@route("/clear_tmp",method="POST")
def clear_tmp():
    files = os.listdir(temp_path)
    for file_ in files:
        os.remove(file_)    

@route("/css/<css_file>")
def serve_css(css_file):
    return static_file(css_file, os.path.dirname(os.path.abspath(__file__))+os.path.sep+"css")

@route("/")
def serve_web():
    return static_file("index.html", os.path.dirname(os.path.abspath(__file__)))

run(host="0.0.0.0",port=8090)
