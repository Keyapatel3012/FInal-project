
import os
import requests
import re
import hashlib
import urllib
import sqlite3
import argparse
import image_lib
import inspect
from pathlib import Path
import datetime
import sys

# declare the Global variables
image_cache_directory = None  # path of image cache main folder
image_cache_database = None   # path of image cache main database
api_key_amod = '5NsjD0T4jy1EKvJx4ZPQryKAlrbnsLIE8YAOsBDz'

def main():
    # Get the APOD date from the argparser command line
    apod_date = get_apod_date()    

    # Get the full main path of the directory in which this script resides
    script_dir = get_script_dir()

    # Initialize the image cache script
    init_apod_cache(script_dir)

    # APOD id for the specified date to the cache
    apod_id = add_apod_to_cache(apod_date)

    # retrive the information for the APOD from the Database
    apod_info = get_apod_info(apod_id)

    # Set the APOD as the desktop background image if apoid is not eqal  0
    if apod_id != 0:
        result = image_lib.set_desktop_background_image(apod_info['img_file_path']) # call the method for set image background
        if result:
            print("Setting desktop to"+apod_info['img_file_path']+" success")
def get_apod_date():
    parser = argparse.ArgumentParser(description='APOD Desktop') # define arg parser
    parser.add_argument('date', nargs='?', default=datetime.date.today().strftime('%Y-%m-%d'),
                    help='APOD date  should be format: YYYY-MM-DD')  # get the date
    args = parser.parse_args()

    # checking the date condition not accepted future date and not accepted 1995 before
    try:
        apod_date = datetime.datetime.strptime(args.date, '%Y-%m-%d').date()
        if apod_date < datetime.date(1995, 6, 16) or apod_date > datetime.date.today():
            raise ValueError()
    except ValueError:
        print('Error: Invalid APOD date specified.')
        print('Script execution aborted')
        sys.exit(1)
    return apod_date



def get_script_dir():
    # get the script path
    script_path = os.path.abspath(inspect.getframeinfo(inspect.currentframe()).filename)
    return os.path.dirname(script_path)


# method for coonction establish with database
def get_db_cursor(image_cache_database):
    # Open database connection
    connection = sqlite3.connect(image_cache_database)
    cursor = connection.cursor()

    return cursor, connection


def close_db_connection(cursor):
    # disconnect from server
    cursor.close()


def init_apod_cache(parent_dir):
    global image_cache_directory
    global image_cache_database

    image_cache_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images') #path of the image cache directory
   
    print(f"Image cache directory: {image_cache_directory}") 
    # Create the image cache directory if it does not already exist
    image_cache_path = Path(image_cache_directory)
    if not image_cache_path.exists():
        image_cache_path.mkdir(parents=True) # make directory
        print(f"Image Cache Directory Created")
    else:
        print(f"Image Cache Directory already exists.")

    # path of image cache database
    image_cache_database = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images', 'apod_project.db')
    print(f"Image cache database: {image_cache_database}") 

    # Create the database if it does not already exist
    if not os.path.exists(image_cache_database):
        os.makedirs(os.path.dirname(image_cache_database), exist_ok=True) # database creation
        print("Image Cache DB Created")
    else:
        print("Image Cache DB already exists.")    


    # Connect to the SQLite database 
    c,connection= get_db_cursor(image_cache_database)  # call method for connect to database

    #create the table if it doesn't already exist
    c.execute('''CREATE TABLE IF NOT EXISTS apod_images_data
             (id INTEGER PRIMARY KEY, adob_Title TEXT, adob_Explanation TEXT, adob_Img_File_Path TEXT, hash TEXT)''') 
    
    close_db_connection(c) # close cursor


# SHA-256 hash value
def hash_file(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
        return hashlib.sha256(data).hexdigest()


# for generating a thumbnail for videos
def thumbnail_gen(videos_url):
    main_pattern = r'https://www\.youtube\.com/embed/([a-zA-Z0-9_-]+)\?.*'      
   
    thumb_pattern = r'https://img.youtube.com/vi/\1/0.jpg'  # Define the  for the thumbnail URL
    
    image_url = re.sub(main_pattern, thumb_pattern, videos_url) # replace the pattern in the input URL with the thumbnail URL
    return image_url

# method for retrive data from nasa website date wise
def api_retrive(apod_date):
    apod_img_url = f'https://api.nasa.gov/planetary/apod?api_key={api_key_amod}&date={apod_date.isoformat()}'
    response = requests.get(apod_img_url)
    data_apod = response.json()
    return data_apod  # retune a data

# add data 
def add_apod_to_cache(apod_date):

    print("APOD date : ", apod_date.isoformat()) # print the date

    data_apod =  api_retrive(apod_date) # call the retrive data date wise

    if data_apod['media_type'] == 'image': # if image then execute below part
        image_url = data_apod['hdurl']
        print("Getting "+ apod_date.isoformat() +" APOD information from NASA...success")
        print("APOD title:",data_apod['title']) # print apod title
        print("APOD URL:",image_url) # print a apod image url
        print("Downloading image from ",image_url,"..success") # print a success message
        
        image_title = re.sub(r'[^a-zA-Z0-9\s_]+', '', data_apod['title']).strip().replace(' ', '_') # retrive the image title
        image_file_path = determine_apod_file_path(image_title,image_url) # make a image path
        image_hash = hash_file(image_file_path) if os.path.exists(image_file_path) else None # for making hash file
        if not image_hash:
            image_hash = hash_file(image_file_path)
        print("APOD SHA-256:",image_hash)
        id = get_apod_id_from_db(image_hash)
        if id:
            print('Image already exists in cache.')
            return id[0]
        else:
            new_Last_Img_Id = add_apod_to_db(data_apod['title'], data_apod['explanation'], image_file_path, image_hash)
            print("APOD image is not already in cache.") # print a message
            print("APOD file path:",image_file_path) # print a image file path
            print("Saving image file as ",image_file_path, "...success") # print a saving file message
            print("Adding APOD to image cache DB...success") # print a success message
            return new_Last_Img_Id
        
    # if videos  then execute below part
    else:
        videos_url = data_apod['url'] # get a video url
        image_url = thumbnail_gen(videos_url)  # call method for generate image thumbnail
        print("Getting "+ apod_date.isoformat() +" APOD information from NASA success")  # print a success message
        print("APOD title:",data_apod['title'])  # print apod title
        print("APOD URL:",image_url) # print apod image url
        print("Downloading image from ",image_url,"..success")      # print a success message   
        image_title = re.sub(r'[^a-zA-Z0-9\s_]+', '', data_apod['title']).strip().replace(' ', '_')  # retrive the image title
        image_file_path = determine_apod_file_path(image_title,image_url) # make a image path
        image_hash = hash_file(image_file_path) if os.path.exists(image_file_path) else None    # for making hash file
        if not image_hash:
            image_hash = hash_file(image_file_path)
        print("APOD SHA-256:",image_hash)
        id = get_apod_id_from_db(image_hash)

        if id:
            print('Image already exists in cache.')
            return  id[0]
        else:
            new_Last_Img_Id = add_apod_to_db(data_apod['title'], data_apod['explanation'], image_file_path, image_hash)
            print("APOD image is not already in cache.") # print a message
            print("APOD file path:",image_file_path) # print a image file path
            print("Saving image file as ",image_file_path, "...success")  # print a saving file message
            print("Adding APOD to image cache DB...success")  # print a success message
            return new_Last_Img_Id


    return 0

def add_apod_to_db(title, explanation, file_path, sha256):
    
    # Add the image to the database 
    c,connection= get_db_cursor(image_cache_database) # call method for connect to database
    c.execute('INSERT INTO apod_images_data (adob_Title, adob_Explanation, adob_Img_File_Path, hash) VALUES (?, ?, ?, ?)',
                (title, explanation, file_path, sha256))
    new_Last_Id = c.lastrowid
    connection.commit()
    close_db_connection(c) # close cursor
    return new_Last_Id

def get_apod_id_from_db(image_sha256):
    # get apod id from data base
    c,connection= get_db_cursor(image_cache_database) # call method for connect to database
    c.execute('SELECT id FROM apod_images_data WHERE hash=?', (image_sha256,))
    existing_image_id = c.fetchone()
    connection.commit()
    close_db_connection(c) # close cursor
    return existing_image_id

# making a image file path
def determine_apod_file_path(image_title, image_url):
    image_ext_path = os.path.splitext(urllib.parse.urlparse(image_url).path)[1]
    image_title = re.sub(r'[^a-zA-Z0-9\s_]+', '', image_title).strip().replace(' ', '_')
    image_file_name = "".join([image_title, image_ext_path])
    image_file_path = os.path.join(image_cache_directory, image_file_name)
    response = requests.get(image_url)
    with open(image_file_path, 'wb') as file_loc:
        file_loc.write(response.content)
    return image_file_path


# get a apod information
def get_apod_info(image_id):

    c,connection= get_db_cursor(image_cache_database) # call method for connect to database
    c.execute('SELECT adob_Title, adob_Explanation, adob_Img_File_Path FROM apod_images_data WHERE id = ?', (image_id,))
    result = c.fetchone()

    apod_info = {
                    'title': result[0], 
                    'img_file_path': result[2],
                    'explanation': result[1]
                }
    close_db_connection(c) # close cursor
    return apod_info

def get_all_apod_titles():
    c,connection= get_db_cursor(image_cache_database) # call method for connect to database
    c.execute('SELECT adob_Title from apod_images_data')
    connection.commit()
    result = c.fetchall()
    title_list = [row[0] for row in result]
    data = {'title': title_list}
    close_db_connection(c) # close cursor
    return data

if __name__ == '__main__':
    main()

