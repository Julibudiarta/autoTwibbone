"""
Storage abstraction layer untuk mendukung berbagai backend penyimpanan.
Support: LocalStorage, GoogleDriveStorage, SupabaseStorage
"""

from abc import ABC, abstractmethod
import os
import io
from typing import Optional, BinaryIO
from datetime import datetime


class StorageBackend(ABC):
    """Interface abstrak untuk storage backend."""
    
    @abstractmethod
    def save_file(self, file_path: str, file_content: BinaryIO) -> str:
        """Simpan file dan return path/ID untuk diakses nanti."""
        pass
    
    @abstractmethod
    def get_file(self, file_path: str) -> BinaryIO:
        """Ambil file dari storage."""
        pass
    
    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        """Cek apakah file ada."""
        pass
    
    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """Hapus file."""
        pass
    
    @abstractmethod
    def get_download_url(self, file_path: str) -> str:
        """Dapatkan URL untuk download file."""
        pass
    
    @abstractmethod
    def create_folder(self, folder_path: str) -> str:
        """Buat folder, return folder ID/path."""
        pass


class LocalStorage(StorageBackend):
    """Storage menggunakan filesystem lokal."""
    
    def __init__(self, base_path: str = 'storage'):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
    
    def _get_full_path(self, file_path: str) -> str:
        """Konversi path ke full path."""
        full_path = os.path.join(self.base_path, file_path)
        full_path = os.path.abspath(full_path)
        if not full_path.startswith(os.path.abspath(self.base_path)):
            raise ValueError(f"Path traversal detected: {file_path}")
        return full_path
    
    def save_file(self, file_path: str, file_content: BinaryIO) -> str:
        """Simpan file ke filesystem lokal."""
        full_path = self._get_full_path(file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'wb') as f:
            f.write(file_content.read())
        
        return file_path
    
    def get_file(self, file_path: str) -> BinaryIO:
        """Ambil file dari filesystem."""
        full_path = self._get_full_path(file_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        return open(full_path, 'rb')
    
    def file_exists(self, file_path: str) -> bool:
        """Cek file di filesystem."""
        try:
            full_path = self._get_full_path(file_path)
            return os.path.exists(full_path)
        except ValueError:
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """Hapus file dari filesystem."""
        try:
            full_path = self._get_full_path(file_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
    
    def get_download_url(self, file_path: str) -> str:
        """Return relative path untuk lokal storage."""
        return f"/storage/{file_path}"
    
    def create_folder(self, folder_path: str) -> str:
        """Buat folder di filesystem."""
        full_path = self._get_full_path(folder_path)
        os.makedirs(full_path, exist_ok=True)
        return folder_path


class SupabaseStorage(StorageBackend):
    """Storage menggunakan Supabase (PostgreSQL + Storage bucket)."""
    
    def __init__(self, supabase_url: str, supabase_key: str, bucket_name: str = 'twibbon-files'):
        """
        Inisialisasi Supabase storage.
        
        Args:
            supabase_url: URL Supabase project (https://xxx.supabase.co)
            supabase_key: API key Supabase
            bucket_name: Nama bucket di Supabase Storage
        """
        try:
            from supabase import create_client, Client
        except ImportError:
            raise ImportError(
                "Supabase dependencies tidak terinstall. "
                "Install dengan: pip install supabase"
            )
        
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.bucket_name = bucket_name
        
        # Initialize Supabase client
        self.client: 'Client' = create_client(supabase_url, supabase_key)
    
    def save_file(self, file_path: str, file_content: BinaryIO) -> str:
        """Simpan file ke Supabase Storage."""
        try:
            file_data = file_content.read()
            
            # Upload ke bucket
            response = self.client.storage.from_(self.bucket_name).upload(
                file_path,
                file_data,
                file_options={"upsert": "true"}
            )
            
            return file_path
        except Exception as e:
            print(f"Error saving file to Supabase: {e}")
            raise
    
    def get_file(self, file_path: str) -> BinaryIO:
        """Ambil file dari Supabase Storage."""
        try:
            response = self.client.storage.from_(self.bucket_name).download(file_path)
            return io.BytesIO(response)
        except Exception as e:
            print(f"Error getting file from Supabase: {e}")
            raise FileNotFoundError(f"File not found: {file_path}")
    
    def file_exists(self, file_path: str) -> bool:
        """Cek apakah file ada di Supabase."""
        try:
            # List files di folder
            file_name = file_path.split('/')[-1]
            folder_path = '/'.join(file_path.split('/')[:-1]) if '/' in file_path else ''
            
            response = self.client.storage.from_(self.bucket_name).list(folder_path)
            
            if response:
                for file in response:
                    if file['name'] == file_name:
                        return True
            return False
        except Exception:
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """Hapus file dari Supabase."""
        try:
            self.client.storage.from_(self.bucket_name).remove([file_path])
            return True
        except Exception as e:
            print(f"Error deleting file from Supabase: {e}")
            return False
    
    def get_download_url(self, file_path: str) -> str:
        """Dapatkan public URL untuk download file dari Supabase."""
        try:
            url = self.client.storage.from_(self.bucket_name).get_public_url(file_path)
            return url
        except Exception as e:
            print(f"Error getting download URL: {e}")
            return None
    
    def create_folder(self, folder_path: str) -> str:
        """
        Buat folder di Supabase (sebenarnya hanya membuat path kosong).
        Supabase tidak memerlukan folder creation eksplisit.
        """
        return folder_path


class GoogleDriveStorage(StorageBackend):
    """Storage menggunakan Google Drive API."""
    
    def __init__(self, credentials_file: str = 'credentials.json', 
                 token_file: str = 'token.pickle',
                 root_folder_id: str = 'root'):
        """
        Inisialisasi Google Drive storage.
        
        Args:
            credentials_file: Path ke credentials.json dari Google Cloud Console
            token_file: Path untuk menyimpan token akses
            root_folder_id: ID folder di Google Drive untuk menyimpan data
        """
        try:
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.exceptions import RefreshError
            import pickle
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
        except ImportError:
            raise ImportError(
                "Google Drive dependencies tidak terinstall. "
                "Install dengan: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
            )
        
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.root_folder_id = root_folder_id
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        
        self.Request = Request
        self.InstalledAppFlow = InstalledAppFlow
        self.pickle = pickle
        self.RefreshError = RefreshError
        self.build = build
        self.MediaFileUpload = MediaFileUpload
        self.MediaIoBaseDownload = MediaIoBaseDownload
        
        self.service = self._authenticate()
        self._folder_cache = {}
    
    def _authenticate(self):
        """Autentikasi dengan Google Drive API."""
        creds = None
        
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = self.pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(self.Request())
                except self.RefreshError:
                    creds = None
            
            if not creds:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_file}\n"
                        "Ambil dari: https://console.cloud.google.com/apis/credentials"
                    )
                
                flow = self.InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_file, 'wb') as token:
                self.pickle.dump(creds, token)
        
        return self.build('drive', 'v3', credentials=creds)
    
    def _get_or_create_folder(self, folder_path: str) -> str:
        """Dapatkan atau buat folder nested di Google Drive."""
        if folder_path in self._folder_cache:
            return self._folder_cache[folder_path]
        
        parts = folder_path.split('/')
        current_parent_id = self.root_folder_id
        current_path = ""
        
        for part in parts:
            if not part:
                continue
            
            current_path = f"{current_path}/{part}" if current_path else part
            
            if current_path in self._folder_cache:
                current_parent_id = self._folder_cache[current_path]
                continue
            
            query = (f"name='{part}' and mimeType='application/vnd.google-apps.folder' "
                    f"and '{current_parent_id}' in parents and trashed=false")
            results = self.service.files().list(
                q=query, spaces='drive', fields='files(id, name)', pageSize=1
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                current_parent_id = files[0]['id']
            else:
                file_metadata = {
                    'name': part,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [current_parent_id]
                }
                folder = self.service.files().create(
                    body=file_metadata, fields='id'
                ).execute()
                current_parent_id = folder.get('id')
            
            self._folder_cache[current_path] = current_parent_id
        
        return current_parent_id
    
    def create_folder(self, folder_path: str) -> str:
        """Buat folder di Google Drive."""
        folder_id = self._get_or_create_folder(folder_path)
        return folder_id
    
    def save_file(self, file_path: str, file_content: BinaryIO) -> str:
        """Simpan file ke Google Drive."""
        parts = file_path.rsplit('/', 1)
        
        if len(parts) == 2:
            folder_path, filename = parts
            parent_id = self._get_or_create_folder(folder_path)
        else:
            filename = file_path
            parent_id = self.root_folder_id
        
        query = f"name='{filename}' and '{parent_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query, spaces='drive', fields='files(id)', pageSize=1
        ).execute()
        
        files = results.get('files', [])
        file_content.seek(0)
        
        file_metadata = {'name': filename, 'parents': [parent_id]}
        media = self.MediaFileUpload(file_content, mimetype='application/octet-stream')
        
        if files:
            file_id = files[0]['id']
            self.service.files().update(
                fileId=file_id,
                body=file_metadata,
                media_body=media
            ).execute()
        else:
            self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
        
        return file_path
    
    def get_file(self, file_path: str) -> BinaryIO:
        """Ambil file dari Google Drive."""
        parts = file_path.rsplit('/', 1)
        
        if len(parts) == 2:
            folder_path, filename = parts
            parent_id = self._get_or_create_folder(folder_path)
        else:
            filename = file_path
            parent_id = self.root_folder_id
        
        query = f"name='{filename}' and '{parent_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query, spaces='drive', fields='files(id)', pageSize=1
        ).execute()
        
        files = results.get('files', [])
        if not files:
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_id = files[0]['id']
        file_io = io.BytesIO()
        
        request = self.service.files().get_media(fileId=file_id)
        downloader = self.MediaIoBaseDownload(file_io, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        file_io.seek(0)
        return file_io
    
    def file_exists(self, file_path: str) -> bool:
        """Cek apakah file ada di Google Drive."""
        try:
            parts = file_path.rsplit('/', 1)
            
            if len(parts) == 2:
                folder_path, filename = parts
                parent_id = self._get_or_create_folder(folder_path)
            else:
                filename = file_path
                parent_id = self.root_folder_id
            
            query = f"name='{filename}' and '{parent_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query, spaces='drive', fields='files(id)', pageSize=1
            ).execute()
            
            return len(results.get('files', [])) > 0
        except Exception:
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """Hapus file dari Google Drive."""
        try:
            parts = file_path.rsplit('/', 1)
            
            if len(parts) == 2:
                folder_path, filename = parts
                parent_id = self._get_or_create_folder(folder_path)
            else:
                filename = file_path
                parent_id = self.root_folder_id
            
            query = f"name='{filename}' and '{parent_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query, spaces='drive', fields='files(id)', pageSize=1
            ).execute()
            
            files = results.get('files', [])
            if files:
                self.service.files().delete(fileId=files[0]['id']).execute()
                return True
            return False
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
    
    def get_download_url(self, file_path: str) -> str:
        """Return shared link untuk file di Google Drive."""
        parts = file_path.rsplit('/', 1)
        
        if len(parts) == 2:
            folder_path, filename = parts
            parent_id = self._get_or_create_folder(folder_path)
        else:
            filename = file_path
            parent_id = self.root_folder_id
        
        query = f"name='{filename}' and '{parent_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query, spaces='drive', fields='files(id)', pageSize=1
        ).execute()
        
        files = results.get('files', [])
        if not files:
            return None
        
        file_id = files[0]['id']
        
        try:
            self.service.permissions().create(
                fileId=file_id,
                body={'role': 'reader', 'type': 'anyone'}
            ).execute()
        except:
            pass
        
        return f"https://drive.google.com/uc?export=download&id={file_id}"


def create_storage(backend: str = 'local', **kwargs) -> StorageBackend:
    """
    Factory untuk membuat storage backend.
    
    Args:
        backend: 'local', 'google_drive', atau 'supabase'
        **kwargs: argumen untuk backend
    
    Returns:
        StorageBackend instance
    
    Contoh:
        storage = create_storage('local', base_path='uploads')
        storage = create_storage('google_drive', credentials_file='credentials.json')
        storage = create_storage('supabase', 
            supabase_url='https://xxx.supabase.co',
            supabase_key='your_key',
            bucket_name='twibbon-files')
    """
    if backend == 'local':
        return LocalStorage(**kwargs)
    elif backend == 'google_drive':
        return GoogleDriveStorage(**kwargs)
    elif backend == 'supabase':
        return SupabaseStorage(**kwargs)
    else:
        raise ValueError(f"Unknown backend: {backend}")
