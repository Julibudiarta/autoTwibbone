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

    @abstractmethod
    def cleanup_if_needed(self, threshold_bytes: int = 900 * 1024 * 1024, target_bytes: int = 500 * 1024 * 1024):
        """Hapus otomatis file terlama jika ukuran total melebihi threshold_bytes hingga menyisakan target_bytes."""
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
        return f"/serve/{file_path}"
    
    def create_folder(self, folder_path: str) -> str:
        """Buat folder di filesystem."""
        full_path = self._get_full_path(folder_path)
        os.makedirs(full_path, exist_ok=True)
        return folder_path

    def cleanup_if_needed(self, threshold_bytes: int = 900 * 1024 * 1024, target_bytes: int = 500 * 1024 * 1024):
        """Hapus otomatis file terlama di lokal storage jika > 900MB hingga menyisakan <= 500MB."""
        try:
            files_info = []
            total_size = 0
            for root, _, files in os.walk(self.base_path):
                for f in files:
                    full_path = os.path.join(root, f)
                    try:
                        stat = os.stat(full_path)
                        size = stat.st_size
                        mtime = stat.st_mtime
                        rel_path = os.path.relpath(full_path, self.base_path).replace('\\', '/')
                        files_info.append({
                            'path': rel_path,
                            'full_path': full_path,
                            'size': size,
                            'mtime': mtime
                        })
                        total_size += size
                    except OSError:
                        pass

            threshold_mb = threshold_bytes / (1024 * 1024)
            target_mb = target_bytes / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)

            if total_size > threshold_bytes:
                print(f"[Local Storage Cleanup] Storage ({total_mb:.1f} MB) melebihi batas {threshold_mb:.0f} MB. Membersihkan hingga {target_mb:.0f} MB...")
                files_info.sort(key=lambda x: x['mtime'])  # Terlama dulu
                deleted_count = 0
                for item in files_info:
                    if total_size <= target_bytes:
                        break
                    try:
                        os.remove(item['full_path'])
                        total_size -= item['size']
                        deleted_count += 1
                    except OSError as e:
                        print(f"[Local Cleanup] Error menghapus {item['path']}: {e}")
                print(f"[Local Storage Cleanup] Selesai. Dihapus: {deleted_count} file. Ukuran baru: {total_size / (1024 * 1024):.1f} MB.")
        except Exception as e:
            print(f"[Local Storage Cleanup Error] {e}")


class SupabaseStorage(StorageBackend):
    """Storage menggunakan Supabase Storage bucket."""
    
    def __init__(self, supabase_url: str, supabase_key: str, bucket_name: str = 'twibbon-files'):
        try:
            from supabase import create_client
        except ImportError:
            raise ImportError(
                "Supabase dependencies tidak terinstall. "
                "Install dengan: pip install supabase"
            )
        
        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL dan SUPABASE_KEY harus diisi di file .env"
            )
        
        self.supabase_url = supabase_url.rstrip('/')
        self.supabase_key = supabase_key
        self.bucket_name = bucket_name
        self.client = create_client(supabase_url, supabase_key)
        print(f"SupabaseStorage: terhubung ke {supabase_url}, bucket='{bucket_name}'")
    
    def _guess_mime(self, file_path: str) -> str:
        """Tebak MIME type dari ekstensi file."""
        ext = file_path.rsplit('.', 1)[-1].lower() if '.' in file_path else ''
        mime_map = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'zip': 'application/zip',
        }
        return mime_map.get(ext, 'image/png')

    def save_file(self, file_path: str, file_content: BinaryIO) -> str:
        """Upload file ke Supabase Storage (upsert=true agar bisa overwrite)."""
        file_data = file_content.read()
        mime = self._guess_mime(file_path)
        try:
            self.client.storage.from_(self.bucket_name).upload(
                path=file_path,
                file=file_data,
                file_options={'content-type': mime, 'upsert': 'true'}
            )
        except Exception as e:
            err_str = str(e).lower()
            if any(k in err_str for k in ('403', 'row-level security', 'violates', 'unauthorized', 'forbidden')):
                # 1. Coba update()
                try:
                    self.client.storage.from_(self.bucket_name).update(
                        path=file_path,
                        file=file_data,
                        file_options={'content-type': mime}
                    )
                    return file_path
                except Exception:
                    pass

                # 2. Coba remove lalu upload
                try:
                    self.client.storage.from_(self.bucket_name).remove([file_path])
                    self.client.storage.from_(self.bucket_name).upload(
                        path=file_path,
                        file=file_data,
                        file_options={'content-type': mime}
                    )
                    return file_path
                except Exception as e3:
                    raise RuntimeError(
                        f"Supabase RLS Policy Error: Bucket '{self.bucket_name}' menolak izin UPDATE/DELETE. "
                        f"Buka Supabase Dashboard > Storage > Policies > izinkan UPDATE/DELETE untuk anon role."
                    ) from e3

            elif any(k in err_str for k in ('already exists', 'duplicate', '409')):
                try:
                    self.client.storage.from_(self.bucket_name).remove([file_path])
                    self.client.storage.from_(self.bucket_name).upload(
                        path=file_path,
                        file=file_data,
                        file_options={'content-type': mime}
                    )
                except Exception as e2:
                    raise RuntimeError(f"Supabase upload gagal (retry): {e2}") from e2
            else:
                raise RuntimeError(f"Supabase upload gagal: {e}") from e
        return file_path
    
    def get_file(self, file_path: str) -> BinaryIO:
        """Download file dari Supabase Storage."""
        try:
            data = self.client.storage.from_(self.bucket_name).download(file_path)
            return io.BytesIO(data)
        except Exception as e:
            raise FileNotFoundError(f"File tidak ditemukan di Supabase: {file_path}") from e
    
    def file_exists(self, file_path: str) -> bool:
        """Cek apakah file ada di Supabase."""
        try:
            folder = '/'.join(file_path.split('/')[:-1]) if '/' in file_path else ''
            name   = file_path.split('/')[-1]
            files  = self.client.storage.from_(self.bucket_name).list(folder or '')
            return any(isinstance(f, dict) and f.get('name') == name for f in (files or []))
        except Exception:
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """Hapus file dari Supabase."""
        try:
            self.client.storage.from_(self.bucket_name).remove([file_path])
            return True
        except Exception as e:
            print(f"Supabase delete error: {e}")
            return False
    
    def get_download_url(self, file_path: str) -> str:
        """
        Kembalikan public URL untuk mengakses file.
        Bucket HARUS di-set ke 'Public' di Supabase Dashboard.
        """
        url = self.client.storage.from_(self.bucket_name).get_public_url(file_path)
        return str(url)
    
    def create_folder(self, folder_path: str) -> str:
        """
        Supabase Storage tidak butuh pembuatan folder eksplisit.
        """
        return folder_path

    def _get_all_files(self, path: str = '') -> list:
        all_files = []
        try:
            res = self.client.storage.from_(self.bucket_name).list(path, {'limit': 1000})
            for item in res or []:
                if not isinstance(item, dict) or not item.get('name'):
                    continue
                name = item.get('name')
                item_path = f"{path}/{name}" if path else name
                metadata = item.get('metadata')
                if metadata and isinstance(metadata, dict) and 'size' in metadata:
                    all_files.append({
                        'name': name,
                        'path': item_path,
                        'size': metadata.get('size', 0),
                        'created_at': item.get('created_at') or item.get('updated_at') or ''
                    })
                else:
                    all_files.extend(self._get_all_files(item_path))
        except Exception as e:
            print(f"[Supabase List Error] {e}")
        return all_files

    def cleanup_if_needed(self, threshold_bytes: int = 900 * 1024 * 1024, target_bytes: int = 500 * 1024 * 1024):
        """Hapus otomatis file terlama jika ukuran total > 900MB hingga menyisakan <= 500MB."""
        try:
            files = self._get_all_files('')
            total_bytes = sum(f['size'] for f in files)
            threshold_mb = threshold_bytes / (1024 * 1024)
            target_mb = target_bytes / (1024 * 1024)
            total_mb = total_bytes / (1024 * 1024)

            if total_bytes > threshold_bytes:
                print(f"[Supabase Cleanup] Storage ({total_mb:.1f} MB) melebihi batas {threshold_mb:.0f} MB. Membersihkan hingga {target_mb:.0f} MB...")
                files.sort(key=lambda x: x['created_at'])

                to_delete = []
                current_size = total_bytes
                for f in files:
                    if current_size <= target_bytes:
                        break
                    to_delete.append(f['path'])
                    current_size -= f['size']

                if to_delete:
                    for i in range(0, len(to_delete), 100):
                        batch = to_delete[i:i + 100]
                        self.client.storage.from_(self.bucket_name).remove(batch)
                    print(f"[Supabase Cleanup] Berhasil menghapus {len(to_delete)} file terlama. Ukuran baru: {current_size / (1024 * 1024):.1f} MB.")
        except Exception as e:
            print(f"[Supabase Cleanup Error] {e}")


class GoogleDriveStorage(StorageBackend):
    """Storage menggunakan Google Drive API."""
    
    def __init__(self, credentials_file: str = 'credentials.json', 
                 token_file: str = 'token.pickle',
                 root_folder_id: str = 'root'):
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
        return self._get_or_create_folder(folder_path)
    
    def save_file(self, file_path: str, file_content: BinaryIO) -> str:
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

    def cleanup_if_needed(self, threshold_bytes: int = 900 * 1024 * 1024, target_bytes: int = 500 * 1024 * 1024):
        pass


class BrowserStorage(StorageBackend):
    """Storage sementara di RAM memori server/browser (ephemeral).
    File TIDAK PERNAH disimpan ke disk lokal maupun Supabase Cloud.
    Sangat cepat, tanpa latency I/O disk atau upload network cloud.
    """
    def __init__(self):
        self._store = {}
        self._folders = set()
        print("BrowserStorage (Memory): Mode penyimpanan super cepat aktif (tanpa simpan ke disk/cloud)")

    def save_file(self, file_path: str, file_content: BinaryIO) -> str:
        try:
            file_content.seek(0)
        except Exception:
            pass
        data = file_content.read()
        self._store[file_path] = {
            'data': data,
            'mtime': datetime.now().timestamp(),
            'size': len(data)
        }
        return file_path

    def get_file(self, file_path: str) -> BinaryIO:
        if file_path not in self._store:
            raise FileNotFoundError(f"File tidak ditemukan di RAM memori: {file_path}")
        return io.BytesIO(self._store[file_path]['data'])

    def file_exists(self, file_path: str) -> bool:
        return file_path in self._store

    def delete_file(self, file_path: str) -> bool:
        if file_path in self._store:
            del self._store[file_path]
            return True
        return False

    def get_download_url(self, file_path: str) -> str:
        return f"/serve/{file_path}"

    def create_folder(self, folder_path: str) -> str:
        self._folders.add(folder_path)
        return folder_path

    def cleanup_if_needed(self, threshold_bytes: int = 900 * 1024 * 1024, target_bytes: int = 500 * 1024 * 1024):
        try:
            total_size = sum(item['size'] for item in self._store.values())
            threshold_mb = threshold_bytes / (1024 * 1024)
            target_mb = target_bytes / (1024 * 1024)

            if total_size > threshold_bytes:
                print(f"[Browser Storage Cleanup] RAM Memori ({total_size / (1024*1024):.1f} MB) melebihi {threshold_mb:.0f} MB. Membersihkan RAM...")
                sorted_items = sorted(self._store.items(), key=lambda x: x[1]['mtime'])
                deleted_count = 0
                for path, item in sorted_items:
                    if total_size <= target_bytes:
                        break
                    del self._store[path]
                    total_size -= item['size']
                    deleted_count += 1
                print(f"[Browser Storage Cleanup] Dihapus {deleted_count} file dari RAM. Ukuran baru RAM: {total_size / (1024*1024):.1f} MB.")
        except Exception as e:
            print(f"[Browser Storage Cleanup Error] {e}")


def create_storage(backend: str = 'local', **kwargs) -> StorageBackend:
    b = str(backend).strip().lower()
    if b in ('browser', 'memory', 'ram', 'temp'):
        return BrowserStorage()
    elif b == 'local':
        return LocalStorage(**kwargs)
    elif b == 'google_drive':
        return GoogleDriveStorage(**kwargs)
    elif b == 'supabase':
        return SupabaseStorage(**kwargs)
    else:
        raise ValueError(f"Unknown backend: {backend}")

