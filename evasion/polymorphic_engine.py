import random
import string
from core.config_manager import ConfigManager

class PolymorphicEngine:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.junk_density = self.config.get('evasion.polymorphic.junk_code_density', 0.3)

    def generate_payload(self, original_code: str) -> str:
        """Transforms original code into polymorphic form."""
        # 1. Add junk code
        junk_code = self._generate_junk_code(int(len(original_code) * self.junk_density))
        
        # 2. Obfuscate with XOR (Simple implementation)
        # In production, use a stronger algorithm like Vigenere or AES
        obfuscated = self._xor_encode(original_code, "SURV")
        
        return f"{junk_code}\n{obfuscated}"

    def _generate_junk_code(self, num_lines: int) -> str:
        junk = []
        for _ in range(num_lines):
            junk.append(f"// {random.choice(['NOP', 'Dummy', 'Comment', 'Garbage'])}")
            junk.append(f"int dummy_{random.randint(1000, 9999)} = {random.randint(0, 100)};")
        return "\n".join(junk)

    def _xor_encode(self, text: str, key: str) -> str:
        result = []
        for i, char in enumerate(text):
            key_char = key[i % len(key)]
            result.append(chr(ord(char) ^ ord(key_char)))
        return "".join(result)