#Import libraries
from socket import *                #Socket library
from urllib.parse import urlparse   #Urlparse function from urllib libray
import sys                          #For parsing argument (port number) only
from pathlib import Path            #For folder access (creating and reading)

#To a create a new cache directory
def create_cache_directory(cache_folder):

    #Get the current working directory using Path.cwd() and append './cache' 
    #cwd is of PosixDirectoryType thus, '/'used to concatenate such path
    cache_dir = Path.cwd() / cache_folder    

    #Create the cache directory when it doesn't exist
    #(parents=True:create parent dir without throwing exception;if dir is absent)
    #(exists_ok=True:no exception thrown when path already exists in dir)
    cache_dir.mkdir(parents=True, exist_ok=True) 

    return cache_dir


#Read the requested file from cache
def read_cache(cache_dir_path, url_hostname, url_path):

    #Construct the full path to the file by combining cache directory path ,hostname and path taken from url
    #Append.to join host(ex: zhiju.me)&path(ex:/networks/valid.html)to cache dir in next line.
    file = './' + url_hostname + url_path   
    file = cache_dir_path / file       
    #(ex: file =  /xxx/yyy/cache/zhiju.me/networks/valid.html)

    #Check if the file exists in cache
    if file.is_file():
        #Open the file from cache
        with open(file, 'rb') as cache_file:     #rb- read 'binary file'
            cached_read_data = cache_file.read() #read the file contents

        #Extract html data/msg and html status line ; set read_cache_flag
        cached_read_data, status_code, status_line = get_html_status_and_data(cached_read_data, read_cache_flag = 'X')     

        #Concatenate html status line; success of Cache-Hit = 1; HTML body- for client to read 
        cached_read_data = f"\r\n{status_line} \r\nCache-Hit: 1 \r\n\r\n{cached_read_data}\r\n\r\n" 
        return cached_read_data
    
    #If no file exists in the cache
    return None          


#Write/Store files in cache
def write_cache(cache_data, cache_dir_path, hostname, path):

    #Create cache folders/subfolders

    #Split the path and get the filename.html from the request
    #ex: file = 'valid.html' from path = /networks/valid.html
    html_file_name = path.split('/')[-1]   

    #Get the path excluding filename.html  ,ex: /networks/       
    path_without_file = '/'.join(path.split('/')[:-1]) + '/'  

    #Append . to join host & path_without_file ex: './zhiju.me/networks/
    path = './' + hostname + path_without_file  

    #Join the complete path using the cache directory path & newly created path above
    path = cache_dir_path / path     #ex: /xxx/yyy/cache/zhiju.me/networks/

    #Create folders and sub folders in the specified path
    path.mkdir(parents=True, exist_ok=True)      

    #Create the cache file path within the subfolder
    #ex: /xxx/yyy/cache/zhiju.me/networks/valid.html 
    file_path = path / html_file_name                  

    #Write/Store cache data into the html file created in sub folder
    try:
        with open(file_path, 'wb') as cache_file:
            cache_file.write(cache_data)
        return True
    except:
        return False


#Extract html status line, status code and data from the headers of the response
def get_html_status_and_data(response, read_cache_flag):
    response_str = response.decode() #binary to str

    #if'read_cache'function is asking for information; file is found and status is already 200!
    if read_cache_flag == 'X':    
        status_line = 'HTTP/1.1 200 OK'
        status_code = '200'
        s_data = response_str

    else:   
        #If origin server is asking for information-

        #Extract the html status by splitting the response from the first line break
        #ex:status_line = HTTP/1.1 200 OK
        status_line, other_lines = response_str.split('\r\n', 1)  

        #Extract the body from the html response by splitting the response using double line breaks towards the end
        #ex:s_data='this is the page content for status 200!'
        other_lines, s_data = response_str.split('\r\n\r\n', 1)  

        #Extract the html status code from the status_line 
        #ex:status_code = 200 / 404 / 500
        status_code = status_line.split(' ')[1]              

    return s_data, status_code, status_line


#Get data from origin web server
def call_origin_server(hostname, port, server_request):

    #Create Socket for original web server to accept requests from proxy server
    Server_Socket = socket(AF_INET, SOCK_STREAM)                        
    Server_Socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

    try:
        #Connect the socket to the web
        Server_Socket.connect((hostname, port))

        #Forward the proxy's request to the web server
        Server_Socket.send(server_request.encode())

        #To append/concatenate chunks of server's response in binary format
        s_response = b""    

        #Receive the server's response- data may arrive in chunks; size of the data is unknown
        while True:
            recv_data = Server_Socket.recv(2048)
            if not recv_data:
                break
            s_response += recv_data

        #Extract from the server's response-body/msg,status code'ex: 200'and status line'Ex:HTTP/1.1 200 OK'
        s_data, status_code, status_line = get_html_status_and_data(s_response, read_cache_flag = '')
 
        #Set the response that needs to be sent to the main client
        if status_code == "200":    #success
            server_response = f"\r\n\r\n{status_line} \r\nCache-Hit: 0 \r\n\r\n{s_data}\r\n\r\n"

            #The server's complete response in binary format is saved to be later written in cache.
            cache_data = s_data.encode()
        
        elif status_code == "404":  #page not found error
            server_response = f"\r\n\r\n{status_line} \r\nCache-Hit: 0 \r\n\r\n404 NOT FOUND\r\n\r\n"
            cache_data = None
        
        else:   #500 or other errors
            server_response = f"\r\n\r\nHTTP/1.1 500 INTERNAL ERROR \r\nCache-Hit: 0 \r\n\r\nUnsupported Error\r\n\r\n" 
            cache_data = None
            
    except: 
        #when the main client enters malformed request, handle exceptions
        status_code = '500'
        server_response = f"\r\n\r\nHTTP/1.1 500 INTERNAL ERROR \r\nCache-Hit: 0 \r\n\r\nUnsupported Error\r\n\r\n" 
        cache_data = None
    
    #Close the server's socket connection
    Server_Socket.close()   

    #Pass the server response, status code and cache data back to the proxy server.                              
    return server_response, status_code, cache_data

#Parse Client's request
def parse_client_request(Client_Request):

    #Parse the client's request to get - method, URL, and HTTP version
    Request_Lines = Client_Request.split('\r\n')            #split request lines in an array
    method, url, http_version = Request_Lines[0].split()    #ex: GET; http://zhiju.me/networks/valid.html; HTTP/1.1
    
    #Parse the URL to get Hostname, Path and Port
    Parse_URL = urlparse(url)
    url_hostname = Parse_URL.netloc         #hostname ex: zhiju.me
    url_path = Parse_URL.path               #path ex: /networks/valid.html
    url_port = Parse_URL.port               #port ex: 'None' in our case.

    #Set default port number = 80 for origin web server (if no port number is found in the URL)
    if url_port is None:        
        url_port = 80

    return method, url, http_version, url_hostname, url_path, url_port

#Main Method
def main():
    #Read Proxy Server's Port Number from index 1 of the input
    server_port = int(sys.argv[1])    

    #Proxy server's IP address
    server_ip = '127.0.0.1'

    #Create Proxy Server Socket
    Proxy_Socket = socket(AF_INET, SOCK_STREAM)                         
    Proxy_Socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

    #Bind the proxy server's socket with its IP & Port
    Proxy_Socket.bind((server_ip, server_port))                         

    #Listen for incoming TCP client requests - max. 5 by default for pending connections
    Proxy_Socket.listen()                                              

    #Create a new cache directory
    cache_folder = "./cache/"     #name of the cache folder
    cache_dir_path = create_cache_directory(cache_folder)    #receive the full path to the new cache folder        

    while True:
        print('\r\n************** Ready to Serve.. ***************\r\n')
        
        #Accept client request and create a new Connection
        Connection_Socket , Connection_Address = Proxy_Socket.accept()  
        print (f"Received a client connection from: ({Connection_Address[0]} , {Connection_Address[1]})")

        try:
            #Receive the http request from client's socket
            Client_Request = Connection_Socket.recv(1024).decode() 
            print (f"Received a message from this client: {Client_Request} \r\n")         

            #Parse the client's http request to get - method, URL, and HTTP version
            method, url, http_version, url_hostname, url_path, url_port = parse_client_request(Client_Request)

            #Check if the requested file is in the cache by passing the cache directory, host, path -parsed from url
            cache_read_data = read_cache(cache_dir_path, url_hostname, url_path)         
            
            #If no file exists in cache, send a request to web server
            if cache_read_data is None:  
                print('Oops! No Cache Hit! Requesting origin server for the file...')
                print('\r\nSending the following message from proxy to server:')
                
                #Set the request to be sent to the origin server
                server_request = f"{method} {url_path} {http_version}\r\n"  #ex: GET /networks/valid.html HTTP/1.1
                server_request += f"Host: {url_hostname}\r\n"               #ex: Host: zhiju.me
                server_request += "Connection: close\r\n\r\n"               #ex: Connection: close
                print(server_request)

                #Send the request to the origin web server
                server_response, status_code, cache_data = call_origin_server(url_hostname, url_port, server_request) 
                
                #Set the messages to display for proxy server
                if status_code == "200":    
                    #Success              
                    print('Response received from server and the status code is 200! Write to cache, save time next time...\r\n')
                    
                    #Store the file/response in Cache
                    cache_response = write_cache(cache_data, cache_dir_path, url_hostname, url_path)
                    
                    #If the file is successfully stored in the cache
                    if cache_response:  
                        print('Now responding to client..\r\nAll Done! Closing Socket..')
                    else:
                        print('Cache writing not successful.') 

                elif status_code == "404" or status_code == "500":  
                    #Page not found or any other internal error
                    print('Response received from server but the status code is not 200! No cache writing...')
                    print('\r\nNow responding to client..\r\nAll Done! Closing Socket..')
                    
                #Send the web server's response to the main client
                Connection_Socket.send(server_response.encode())

            else:   
                #If file exists in cache, send the response/data back to the client socket
                print('The requested file is found in the Cache and is now sent to the client. \r\nAll done! Closing Socket...')
                Connection_Socket.send(cache_read_data.encode()) 
        
        except: 
            #When client enters malformed request or some internal error arises, handle exceptions
            print('Unsupported Error! \r\n\r\nNow responding to client..\r\nAll Done! Closing Socket..')
            response = f"\r\n\r\nHTTP/1.1 500 INTERNAL ERROR \r\nCache-Hit: 0 \r\n\r\nUnsupported Error\r\n\r\n" 
            Connection_Socket.send(response.encode())

        #Close the client's socket connection
        Connection_Socket.close()  

#Call main method
if __name__== "__main__":
    main()
