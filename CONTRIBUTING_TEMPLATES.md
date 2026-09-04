# 🚀 Contributing Community Mission Templates

Thank you for helping fellow technical professionals pilot their careers! By contributing a `.qv-mission.yaml` template, you share battle-tested matching strategies, keyword priorities, and narrative weightings for your domain.

---

## 🛠️ Quickstart: 4 Steps to Submit a Template

### 1. Fork & Clone
Fork the `questvector` repository on GitHub and clone it to your local machine:
```bash
git clone https://github.com/YOUR-USERNAME/questvector.git
cd questvector
```

### 2. Copy the Boilerplate
Create a new `.yaml` file inside the `templates/community/` directory using our starter template:
```bash
cp templates/boilerplate.yaml templates/community/sr-cloud-architect.yaml
```

### 3. Build & Validate
Edit your YAML file with your domain-specific keyword banks, narrative weightings, and metric triggers. Then, run the local validation check:
```bash
qv template validate templates/community/sr-cloud-architect.yaml
```
> **Note:** The validator checks YAML syntax, verifies required fields, and ensures your narrative weightings equal **100% (1.00)**.

### 4. Open Your Pull Request
Commit your changes, push to your fork, and submit a Pull Request to `main` with a title like:  
`feat(templates): add Senior Cloud Architect mission template`

---

## 📋 Template Boilerplate (`templates/boilerplate.yaml`)

```yaml
schema_version: "1.0"
mission_id: "your-role-id" # e.g., sr-cloud-architect
metadata:
  title: "Your Target Role Title"
  author: "Your GitHub Username or Name"
  version: "1.0.0"
  description: "A brief summary of who this template is for and what career strategies it emphasizes."
  tags: ["cloud", "architecture", "leadership"]

jd_analysis_rules:
  priority_keywords:
    - "Primary Skill 1"
    - "Primary Skill 2"
    - "Core Domain Standard"
  gap_detection_threshold: 0.75
  red_flags:
    - "unrealistic requirement 1"
    - "vague job scope"

narrative_weighting:
  capabilities: 0.40   # Technical skills weight (0.00 - 1.00)
  chronology: 0.35     # Career progression weight (0.00 - 1.00)
  impact_stories: 0.25 # STAR narrative wins weight (0.00 - 1.00)
  # Total must sum to 1.00

output_formatting:
  target_page_budget: 2
  tone_style: "executive-tactical"
  cover_letter_template: "modular-assembler-v1"
```

---

## 🎖️ Earn Your Flight Engineer Badge!

Every merged template earns the contributor an official **Flight Engineer** badge on the QuestVector README Hall of Fame!
