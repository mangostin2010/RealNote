import requests

class MarkdownDocClient:
    def __init__(self, server_url):
        self.server_url = server_url.rstrip('/')

    def write_doc(self, doc_id, content):
        if isinstance(content, list):
            content = "\n".join(content)
        url = f"{self.server_url}/api/doc/{doc_id}"
        res = requests.post(url, json={"content": content})
        res.raise_for_status()
        return res.json()

    def read_doc(self, doc_id):
        """
        문서 내용 읽기

        # 문서 읽기
        read_content = client.read_doc(doc_id)
        print("문서 내용:\n", read_content)
        """
        url = f"{self.server_url}/api/doc/{doc_id}"
        res = requests.get(url)
        res.raise_for_status()
        return res.json().get('content', '')

    def download_doc(self, doc_id, save_path):
        """문서 원본 다운로드(.md 파일)
        
        # 문서 다운로드
        client.download_doc(doc_id, f"{doc_id}.md")
        print(f"문서가 {doc_id}.md로 저장되었습니다.")
        """
        url = f"{self.server_url}/doc/{doc_id}/raw"
        res = requests.get(url)
        res.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(res.content)
        return save_path

    def list_docs(self):
        """
        서버에 저장된 모든 노트(문서) ID 목록을 가져옵니다.
        """
        url = f"{self.server_url}/api/docs"
        res = requests.get(url)
        res.raise_for_status()
        return res.json().get('docs', [])

    def exists_doc(self, doc_id):
        """
        특정 노트(문서)가 존재하는지 확인합니다.
        """
        url = f"{self.server_url}/api/doc/{doc_id}"
        res = requests.head(url)
        return res.status_code == 200

# 사용 예시
if __name__ == "__main__":
    client = MarkdownDocClient("http://localhost:5000")
    doc_id = "python_module_test"
    content = """# 모듈화된 파이썬 클라이언트 테스트

이 문서는 파이썬 모듈로 작성 및 덮어쓰기 되었습니다.

- 모듈화
- 함수 호출
- API 연동
"""
    # 문서 덮어쓰기
    result = client.write_doc(doc_id, content)
    print("저장 결과:", result)