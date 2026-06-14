import io
import re
import boto3
from botocore.exceptions import ClientError
from app.config import settings
from pypdf import PdfReader

class S3Service:
    def __init__(self):
        # Configure boto3 to point to MinIO or AWS S3 based on endpoint
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL if settings.S3_ENDPOINT_URL else None
        )
        self.bucket_name = settings.S3_BUCKET_NAME
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket_name)
                print(f"Bucket '{self.bucket_name}' created successfully.")
            except Exception as e:
                print(f"Error creating bucket '{self.bucket_name}': {e}. Continuing locally.")
        except Exception as e:
            print(f"S3 storage unavailable: {e}. API will start with storage marked offline.")

    def is_available(self) -> bool:
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except Exception:
            return False

    def upload_file(self, file_content: bytes, object_key: str) -> str:
        """
        Uploads file to S3 and returns file URI/key.
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=file_content
            )
            return f"s3://{self.bucket_name}/{object_key}"
        except Exception as e:
            raise RuntimeError(f"Failed to upload object to S3: {e}")

    def download_file(self, filename: str) -> bytes:
        """
        Downloads file content from S3.
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=filename)
            return response["Body"].read()
        except Exception as e:
            raise RuntimeError(f"Failed to download {filename} from S3: {e}")

    def convert_to_pdf_text(self, filename: str, content: bytes) -> str:
        """
        Mock implementation of PDF converter. For a production RAG:
        - If already PDF: extract text using PdfReader.
        - If HTML/Markdown/TXT: parse and return clean plain text.
        - If DOCX/PPTX: add a real document parser before enabling in the UI.
        """
        ext = filename.split(".")[-1].lower()
        
        if ext == "pdf":
            try:
                reader = PdfReader(io.BytesIO(content))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text
            except Exception as e:
                raise RuntimeError(f"Failed to parse PDF text: {e}")
                
        elif ext in ["txt", "md", "csv"]:
            return content.decode("utf-8", errors="ignore")
            
        elif ext == "html":
            return content.decode("utf-8", errors="ignore")
            
        else:
            raise ValueError(f"Unsupported document format: .{ext}")

def safe_filename(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or "document"

s3_service = S3Service()
