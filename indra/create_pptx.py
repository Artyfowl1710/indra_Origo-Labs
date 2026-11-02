from pptx import Presentation
from pptx.util import Inches, Pt

p = Presentation()

# Slide 1: Title
slide = p.slides.add_slide(p.slide_layouts[0])
slide.shapes.title.text = "Docker Fundamentals"
slide.placeholders[1].text = "A platform for developing, shipping, and running applications in isolated containers.\n\nProvides consistency across development, staging, and production environments."

# Slide 2: Key Benefits
slide = p.slides.add_slide(p.slide_layouts[5])
slide.shapes.title.text = "Key Benefits"
box = slide.shapes.add_shape(17, 0.5, 0.5, 7.5, 4.5)
box.text = "Portability\nRun anywhere - Linux, macOS, Windows\n\nConsistency\n'Works on my machine' problem solved\n\nResource Efficiency\nShare OS kernel, smaller than VMs\n\nFast Startup\nMilliseconds vs minutes for VMs\n\nScalability\nEasy horizontal scaling"

# Slide 3: Container vs VM
slide = p.slides.add_slide(p.slide_layouts[5])
slide.shapes.title.text = "Container vs Virtual Machine"
table = slide.shapes.add_table(3, 5, 0.5, 0.5, 7.5, 4.5)
table.columns[0].cells[0].text = "Aspect"
table.columns[1].cells[0].text = "Container"
table.columns[2].cells[0].text = "Virtual Machine"
table.columns[3].cells[0].text = ""
table.columns[4].cells[0].text = ""
table.columns[1].cells[1].text = "Shared host kernel"
table.columns[2].cells[1].text = "Full OS included"
table.columns[3].cells[1].text = "Shared host kernel"
table.columns[4].cells[1].text = "Full OS included"
table.columns[1].cells[2].text = "~100 MB"
table.columns[2].cells[2].text = "~10-50 GB"
table.columns[3].cells[2].text = "~100 MB"
table.columns[4].cells[2].text = "~10-50 GB"
table.columns[1].cells[3].text = "Seconds"
table.columns[2].cells[3].text = "Minutes"
table.columns[3].cells[3].text = "Seconds"
table.columns[4].cells[3].text = "Minutes"
table.columns[1].cells[4].text = "Process-level"
table.columns[2].cells[4].text = "Hardware-level"
table.columns[3].cells[4].text = "Process-level"
table.columns[4].cells[4].text = "Hardware-level"

# Slide 4: Image Layers
slide = p.slides.add_slide(p.slide_layouts[5])
slide.shapes.title.text = "Image Layers (Immutable)"
box = slide.shapes.add_shape(17, 0.5, 0.5, 7.5, 3.5)
box.text = "Layer 1: /app - Application code\nLayer 2: /runtime - Node, Python, etc\nLayer 3: /builder - Build tools (npm, pip)\nLayer 4: /deps - Dependencies (packages)\nLayer 5: /base - OS base (Ubuntu/Debian)\nLayer 6: /root - Root filesystem"

# Slide 5: Docker Commands
slide = p.slides.add_slide(p.slide_layouts[0])
slide.shapes.title.text = "Docker Commands"
slide.placeholders[1].text = "pull - Download an image\nbuild - Create an image from Dockerfile\nrun - Start a container\nps - List running containers\nimages - List images\nstop/start/remove - Manage containers\nexec - Run commands in container\nlogs - View container output"

# Slide 6: Best Practices
slide = p.slides.add_slide(p.slide_layouts[5])
slide.shapes.title.text = "Best Practices"
box = slide.shapes.add_shape(17, 0.5, 0.5, 7.5, 3.5)
box.text = "Multi-stage builds - Reduce final image size\nLayer optimization - Order instructions carefully\nSecurity - Scan images for vulnerabilities\nTagging - Use semantic versioning (app:1.0.0)\nDocumentation - Keep Dockerfiles readable"

# Slide 7: Conclusion
slide = p.slides.add_slide(p.slide_layouts[0])
slide.shapes.title.text = "Conclusion"
slide.placeholders[1].text = "Docker revolutionizes application deployment by providing:\n\n- Consistent environments\n- Rapid development cycles\n- Efficient resource utilization\n- Simplified scaling\n\nAdopt Docker to modernize your deployment pipeline."

p.save("/workspace/docker_fundamentals.pptx")
print(f"Saved: /workspace/docker_fundamentals.pptx ({len(p.slides)} slides)")
