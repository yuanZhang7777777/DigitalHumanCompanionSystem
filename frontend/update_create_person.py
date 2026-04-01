import os
import re

file_path = "src/views/CreatePerson.vue"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update clean-pane -> glass-panel
content = content.replace("clean-pane", "glass-panel")
content = content.replace("animate-fade-up", "gsap-stagger-item")

# 2. Update form-section template tags to add gsap-stagger-item
content = content.replace('class="form-section glass-panel"', 'class="form-section glass-panel gsap-stagger-item"')

# 3. Add gsap imports
if "import { gsap } from 'gsap'" not in content:
    content = content.replace(
        "import { digitalPersonAPI } from '../api'",
        "import { digitalPersonAPI } from '../api'\nimport { gsap } from 'gsap'"
    )

# 4. Add nextTick to vue import if missing
if "nextTick" not in content and "import { ref, reactive, onMounted }" in content:
    content = content.replace(
        "import { ref, reactive, onMounted } from 'vue'",
        "import { ref, reactive, onMounted, nextTick } from 'vue'"
    )

# 5. Add GSAP animation in onMounted
on_mounted_str = """onMounted(async () => {
  // GSAP 入场动画
  gsap.fromTo('.gsap-stagger-item', 
    { y: 40, opacity: 0 }, 
    { y: 0, opacity: 1, duration: 0.8, stagger: 0.1, ease: 'power3.out' }
  )"""
content = re.sub(r"onMounted\(async \(\) => \{", on_mounted_str, content)

# 6. Process styles for global dark/glassmorphism theme
# Replace specific hardcoded light mode hex/rgb colors with variables or dark colors
style_replacements = {
    "background: #fef2f2;": "background: rgba(220, 38, 38, 0.1);",
    "border: 1px solid #fecaca;": "border: 1px solid rgba(220, 38, 38, 0.3);",
    "color: var(--c-black);": "color: var(--c-white);",
    "background: var(--c-gray-100);": "background: rgba(255, 255, 255, 0.05);",
    "background: var(--c-gray-50);": "background: rgba(255, 255, 255, 0.02);",
    "border: 1px solid var(--c-gray-100);": "border: 1px solid rgba(255, 255, 255, 0.1);",
    "background: var(--c-white);": "background: var(--glass-bg);",
    "color: var(--c-gray-800);": "color: var(--c-gray-300);",
    "color: var(--c-gray-700);": "color: var(--c-gray-400);",
    "background: var(--bg-surface);": "background: rgba(15, 15, 15, 0.85); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1);",
}

for old, new_val in style_replacements.items():
    content = content.replace(old, new_val)

# Handle the glass-panel class if not exists
if ".glass-panel {" not in content:
    content = content + "\n<style scoped>\n.glass-panel {\n  background: var(--glass-bg);\n  border: 1px solid rgba(255, 255, 255, 0.05);\n  border-radius: var(--radius-lg);\n  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);\n}\n</style>"

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Update complete")
