import boto3
import json
import os
import random
import string
import tempfile
from decouple import config
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from s3_helper_functions import download_folder_contents_from_s3, check_if_folder_exists, is_valid_input
import streamlit as st
from streamlit_chat import message
import openai

# Setup OpenAI
OPENAI_API_KEY = config("OPENAI_API_KEY")
openai.organization = config("OPENAI_ORG_ID")
openai.api_key = config("OPENAI_API_KEY")
openai.api_base = "https://oai.hconeai.com/v1"

# Setup s3 resources
s3 = boto3.resource('s3', 
    aws_access_key_id=config('AWS_ACCESS_KEY_ID'), 
    aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY'))
BUCKET_NAME = config("S3_BUCKET")
INDEX = config("S3_INDEX")
bucket = s3.Bucket(BUCKET_NAME)

# Set to None to load all the pages
MAX_PAGE_SIZE = 100

# Initialise session state variables
st.session_state.setdefault('generated', [])
st.session_state.setdefault('past', [])
st.session_state.setdefault('messages', [
    {"role": "system", "content": "You are a helpful bot assisting the user in understanding a pdf. The system will provide you with relevant sections of text to help you answer the user's question."}
])
st.session_state.setdefault('pdf_index', "")

url_params = st.experimental_get_query_params()

if 'pdf_index' in url_params and "site_params" not in st.session_state:
    pdf_index = url_params['pdf_index']
    if len(pdf_index) == 1 and check_if_folder_exists(BUCKET_NAME, INDEX, pdf_index[0]):
        if not os.path.exists(os.path.join(INDEX, pdf_index[0])):
            download_folder_contents_from_s3(BUCKET_NAME, INDEX, pdf_index[0])
        with open(f"{os.path.join(INDEX, pdf_index[0])}/page_details.json", "r") as f:
            st.session_state['site_params'] = json.load(f)

# Setting page title and header
st.set_page_config(page_title="ChatWith", page_icon="💬")
title = st.session_state.site_params['page_details_title'] if "site_params" in st.session_state else "ChatWith"
st.markdown(f"<h1 style='text-align: center;'>{title}</h1>", unsafe_allow_html=True)

def generate_unique_path(original_path):
    folder_name = os.path.basename(original_path)
    while True:
        random_prefix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        unique_folder_name = random_prefix + '_' + folder_name[:8]  # truncate folder name
        unique_folder_name = unique_folder_name.replace(" ", "")
        if not check_if_folder_exists(BUCKET_NAME, INDEX, unique_folder_name):
            return os.path.join(INDEX, unique_folder_name)

def generate_response(prompt):
    vectorstore = FAISS.load_local(os.path.join(INDEX, st.session_state.site_params['pdf_index']), OpenAIEmbeddings(openai_api_key=config("OPENAI_API_KEY"), headers={"Helicone-Auth": f"Bearer {config('HELICONE_SECRET')}"}))
    get_relevant_sources = vectorstore.similarity_search(prompt, k=2)
    template = f"\n\nUse the information below to help answer the user's question.\n\n{get_relevant_sources[0].page_content}"
    if len(get_relevant_sources) > 1:
        template += f"\n\n{get_relevant_sources[1].page_content}"
    system_source_help = {"role": "system", "content": template}
    st.session_state['messages'].append({"role": "user", "content": prompt})

    # Get Previous messages and append context
    to_send = st.session_state['messages'].copy()
    to_send.insert(-1, system_source_help)

    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=to_send,
        headers={"Helicone-Auth": f"Bearer {config('HELICONE_SECRET')}"}
    )
    response = completion.choices[0].message.content
    st.session_state['messages'].append({"role": "assistant", "content": response})

    return response

if "site_params" not in st.session_state:
    st.warning("This is a prototype. Please do not upload any sensitive pdfs. Max PDF size is 100 pages.")

    file_path = st.file_uploader(label="Upload a PDF file that your chatbot will use", type=['pdf'])
    col1, col2 = st.columns(2)
    with col1:
        page_details_title = st.text_input("What would you like the title of the chat to be?")
    with col2:
        custom_name = st.text_input("Input a custom name for the url or leave it blank and we'll choose something based on the filename:", max_chars=20, key="custom_pdf_index")
        if custom_name:
            if not check_if_folder_exists(BUCKET_NAME, INDEX, custom_name):
                st.write("Index name available!")
            else:
                st.write("Index name taken, please choose another or leave blank to generate a random name")
            if not is_valid_input(custom_name):
                st.error("Please only use letters, numbers and underscores / hyphens")
    # with col2:
    page_details_description = st.text_area("Write a description of your documents for the user to see. You will be able to include links using markdown formatting.", placeholder="This document is about....", height=100)

    if st.button("Index PDF", disabled=not bool(file_path)):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_file:
            tmp_file.write(file_path.read())
            print(f"File saved to {tmp_file.name}")
            loader = PyPDFLoader(tmp_file.name)
            pages = loader.load_and_split()
        # only process pages up to MAX_PAGE_SIZE
        pages = pages[:MAX_PAGE_SIZE]
        # Split the pages into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=1000)
        page_chunks = text_splitter.split_documents(pages)
        # Embed into FAISS
        vectorstore = FAISS.from_documents(page_chunks, OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY, headers={"Helicone-Auth": f"Bearer {config('HELICONE_SECRET')}"}))
        # Double check the folder is still available before saving to s3
        if custom_name and not check_if_folder_exists(BUCKET_NAME, INDEX, custom_name):
            s3_and_local_path = os.path.join(INDEX, custom_name)
        else:
            s3_and_local_path = generate_unique_path(os.path.splitext(file_path.name)[0])
        vectorstore.save_local(os.path.join(s3_and_local_path))
        # Save Page details
        new_page_details = {
            "pdf_index": os.path.basename(s3_and_local_path),
            "page_details_title": page_details_title,
            "document_description": page_details_description,
        }
        with open(f"{s3_and_local_path}/page_details.json", "w") as f:
            json.dump(new_page_details, f)
        for root, dirs, files in os.walk(s3_and_local_path):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, s3_and_local_path)
                bucket.upload_file(local_path, os.path.join(s3_and_local_path, relative_path))
        index_id = os.path.basename(s3_and_local_path)
        st.session_state.pdf_index = index_id

        link = f"{config('PROTOCOL')}://{config('DOMAIN')}/?pdf_index={index_id}"
        st.markdown(f"PDF indexed successfully as **{st.session_state.pdf_index}**. The app to chat with your document can be found here: [{link}]({link}).")

if 'site_params' in st.session_state:
    st.markdown(st.session_state.site_params['document_description'])
    # container for chat history
    response_container = st.container()
    container = st.container()

    with container:
        with st.form(key='my_form', clear_on_submit=True):
            user_input = st.text_area("You:", placeholder="Ask me a question about the document!", key='input', height=100)
            submit_button = st.form_submit_button(label='Send')

        if submit_button and user_input:
            if 'generated' in st.session_state and len(st.session_state['generated']) == 0:
                with response_container:
                    message(user_input, is_user=True, key='first')
            output = generate_response(user_input)
            st.session_state['past'].append(user_input)
            st.session_state['generated'].append(output)

    if st.session_state['generated']:
        with response_container:
            if len(st.session_state['generated']) == 1:
                message(st.session_state["generated"][0], key=str(0))
            else:
                for i in range(len(st.session_state['generated'])):
                    message(st.session_state["past"][i], is_user=True, key=str(i) + '_user')
                    message(st.session_state["generated"][i], key=str(i))
