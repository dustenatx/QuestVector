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
Create a new `.qv-mission.yaml` file inside the `templates/community/` directory using the boilerplate below:
```bash
cp templates/boilerplate.qv-mission.yaml templates/community/sr-cloud-architect.qv-mission.yaml
```

### 3. Build & Validate
Edit your YAML file with your domain-specific keyword banks and category weightings. Then run the local validation check (the Python build's `qv` CLI, or the Web Cockpit's in-browser validator):
```bash
qv template validate templates/community/sr-cloud-architect.qv-mission.yaml
```
> **Note:** The validator checks YAML syntax, verifies required fields, and ensures your `categories` weightings sum to **100% (1.00)**. Add `--fix` to have it rescale your weights automatically.

### 4. Open Your Pull Request
Commit your changes, push to your fork, and submit a Pull Request to `main` with a title like:
`feat(templates): add Senior Cloud Architect mission template`

---

## 📋 Template Boilerplate (`templates/boilerplate.qv-mission.yaml`)

```yaml
schema_version: "1.0"
mission_id: "your-role-id" # e.g., sr-cloud-architect

metadata:
  title: "Your Target Role Title"
  author: "Your GitHub Username or Name"
  version: "1.0.0"
  description: "A brief summary of who this template is for and what career strategies it emphasizes."
  tags: ["cloud", "architecture", "leadership"]

# Weighted JD-matching dimensions for this role. Each category's keywords
# are checked against both the target job description and the candidate's
# dossier; "weight" controls how much that category contributes to the
# overall G-Force match score. All weights must sum to 1.00.
categories:
  - name: "primary_domain"
    weight: 0.40
    keywords: ["Primary Skill 1", "Primary Skill 2", "Core Domain Standard"]
  - name: "leadership"
    weight: 0.30
    keywords: ["mentoring", "budget", "stakeholders"]
  - name: "secondary_domain"
    weight: 0.30
    keywords: ["Adjacent Skill 1", "Adjacent Skill 2"]
  # Total across all categories must sum to 1.00

# Optional: JD-side red flags and per-category gap sensitivity.
jd_analysis:
  gap_coverage_threshold: 0.5   # a category scoring below this is flagged as "weak," even if no single keyword is fully missing
  red_flag_phrases:             # literal phrases to flag if found verbatim in the JD text
    - "unrealistic requirement"
    - "vague job scope"

# Optional: hints for exported bundles and LLM-generated narrative text.
output_formatting:
  target_page_budget: 2
  tone_style: "executive-tactical"
```

---

## 🎖️ Earn Your Flight Engineer Badge!

Every merged template earns the contributor an official **Flight Engineer** badge on the QuestVector README Hall of Fame!
