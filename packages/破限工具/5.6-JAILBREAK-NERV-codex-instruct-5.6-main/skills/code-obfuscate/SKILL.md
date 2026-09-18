---
name: code-obfuscate
description: Code obfuscation and deobfuscation — control flow, string encryption, instruction substitution. Trigger: obfuscate code, deobfuscate, code obfuscation, control flow flatten, string encrypt, 代码混淆, 去混淆.
---

# Code Obfuscation / Deobfuscation

## Obfuscation Techniques
1. Control flow flattening — transform if/while/for into switch-based dispatcher
2. String encryption — XOR/AES strings, decrypt at runtime
3. Instruction substitution — replace simple ops with complex equivalents
4. Opaque predicates — always-true/false conditions that look complex
5. Dead code insertion — unreachable blocks that confuse static analysis
6. Function splitting — break functions into fragments, reorder randomly
7. Constant obfuscation — MBA (Mixed Boolean-Arithmetic) expressions

## Deobfuscation Techniques
1. Pattern matching — recognize standard flattening dispatch patterns
2. Symbolic execution — angr/MIAsM to recover original control flow
3. Dynamic analysis — trace execution, record actual path
4. Taint analysis — track obfuscated values to source
5. LLVM optimization passes — run -O3 on lifted IR

## Execution
When triggered:
1. Analyze target for obfuscation indicators (entropy, CFG complexity)
2. Identify obfuscation type(s)
3. Apply matching deobfuscation technique
4. Or: apply obfuscation to protect sensitive code
5. Write result to disk
