---
name: feedback_git_workflow
description: Hacer git pull antes de commitear y pushear cambios
metadata:
  type: feedback
---

Siempre hacer `git pull` antes de `git commit` + `git push`, incluso si el status muestra "up to date".

**Why:** Puede haber cambios nuevos en el remoto (e.g. Stonex u otros archivos actualizados automáticamente) que no se reflejan en el status local si no se fetcheó recientemente.

**How to apply:** En cualquier flujo de commit: `git pull` → `git add` → `git commit` → `git push`.
