import hashlib
import base64
from typing import Dict, List, Optional

class CoupangSignatureV2:
    """
    Coupang Native Signature V2 implementation.
    Based on analysis of libsignature.so.
    """

    @staticmethod
    def calculate_sha256(data: bytes) -> bytes:
        """Returns the raw SHA-256 digest of the given data."""
        sha = hashlib.sha256()
        sha.update(data)
        return sha.digest()

    def calculate_s1(self, headers: Dict[str, str]) -> bytes:
        """
        Calculates SHA-256 for the Headers section.
        Exact header subset and format need verification via Frida.
        """
        # 임시 구현: User-Agent와 기타 표준 헤더 조합
        header_keys = sorted(['User-Agent', 'Accept-Encoding', 'Content-Type'])
        content = ""
        for key in header_keys:
            if key in headers:
                content += f"{key.lower()}:{headers[key]}\n"
        
        return self.calculate_sha256(content.encode('utf-8'))

    def calculate_s2(self, params: Dict[str, str]) -> bytes:
        """
        Calculates SHA-256 for the Query Parameters section.
        Requires alphabetic sorting of keys.
        """
        sorted_keys = sorted(params.keys())
        query_string = "&".join([f"{k}={params[k]}" for k in sorted_keys])
        
        return self.calculate_sha256(query_string.encode('utf-8'))

    def sign(self, headers: Dict[str, str], params: Dict[str, str]) -> str:
        """
        The Final SHA-256 operation (s1 + s2) and Base64 encoding.
        """
        s1 = self.calculate_s1(headers)
        s2 = self.calculate_s2(params)
        
        # Combine s1 and s2
        combined = s1 + s2
        
        # Final hash
        final_hash = self.calculate_sha256(combined)
        
        # Final signature (Base64)
        return base64.b64encode(final_hash).decode('utf-8')

# Singleton instance for easy access
signature_v2 = CoupangSignatureV2()
