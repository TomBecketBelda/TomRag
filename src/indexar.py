"""
indexar.py — Indexa documentos en la base de datos vectorial.
Ejecuta este script cada vez que añadas documentos nuevos a ./documentos/
"""

import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path
import subprocess
import tempfile
import shutil

# ── Configuración ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR   = str(ROOT_DIR / "documentos")   # Carpeta con tus archivos .txt o .pdf
CHUNK_SIZE = 500              # Caracteres por fragmento
DB_PATH    = str(ROOT_DIR / "vectordb")     # Carpeta donde se guarda la base de datos

# ── Cargar modelo de embeddings (se descarga automáticamente la primera vez) ───
print("⏳ Cargando modelo de embeddings...")
embedder = SentenceTransformer("all-MiniLM-L6-v2")  # Ligero, rápido, local

# ── Conectar / crear base de datos vectorial local ─────────────────────────────
client    = chromadb.PersistentClient(path=DB_PATH)
coleccion = client.get_or_create_collection("documentos")

# ── Funciones de carga ─────────────────────────────────────────────────────────
def cargar_txt(path: Path) -> str:
    """Lee un .txt completo ignorando errores de codificación."""
    return path.read_text(encoding="utf-8", errors="ignore")

def _normalizar_texto(texto: str) -> str:
    """Limpia espacios de fin de línea y recorta huecos en extremos."""
    return "\n".join(line.rstrip() for line in texto.splitlines()).strip()


def _cargar_pdf_pypdf(path: Path) -> str:
    """Extrae texto con `pypdf` comparando modo normal vs layout."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    texto_default = "\n".join((page.extract_text() or "") for page in reader.pages)
    texto_layout = "\n".join(
        (page.extract_text(extraction_mode="layout") or "") for page in reader.pages
    )

    texto_default = _normalizar_texto(texto_default)
    texto_layout = _normalizar_texto(texto_layout)
    return texto_layout if len(texto_layout) > len(texto_default) else texto_default


def _cargar_pdf_pymupdf(path: Path) -> str:
    """Extrae texto de PDF usando PyMuPDF."""
    import fitz  # PyMuPDF

    texto = []
    with fitz.open(str(path)) as doc:
        for page in doc:
            texto.append(page.get_text("text") or "")
    return _normalizar_texto("\n".join(texto))


def _cargar_pdf_pdftotext(path: Path) -> str:
    """Intenta extraer texto con binario `pdftotext` si está instalado."""
    if shutil.which("pdftotext") is None:
        return ""

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return ""
        return _normalizar_texto(tmp_path.read_text(encoding="utf-8", errors="ignore"))
    finally:
        # Limpieza defensiva: evita dejar temporales aunque falle la extracción.
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _cargar_pdf_ocr(path: Path) -> str:
    """Fallback OCR para PDFs escaneados (requiere pdf2image + pytesseract)."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception:
        return ""

    paginas = convert_from_path(str(path), dpi=220)
    partes = []
    for img in paginas:
        txt = pytesseract.image_to_string(img, lang="spa+eng+deu")
        if txt:
            partes.append(txt)
    return _normalizar_texto("\n".join(partes))


def cargar_pdf(path: Path) -> str:
    """Extrae texto de PDF usando varios métodos y fallback OCR."""
    metodos = [
        ("pypdf", _cargar_pdf_pypdf),
        ("pymupdf", _cargar_pdf_pymupdf),
        ("pdftotext", _cargar_pdf_pdftotext),
        ("ocr", _cargar_pdf_ocr),
    ]

    errores = []
    for nombre, fn in metodos:
        try:
            texto = fn(path)
            if len(texto) >= 80:
                # Umbral mínimo para descartar extracciones vacías/ruidosas.
                if nombre == "ocr":
                    print("   ℹ️  PDF leído por OCR (documento escaneado).")
                return texto
        except Exception as e:
            errores.append(f"{nombre}: {e}")

    if errores:
        print("   ⚠️  Falló la extracción PDF:", " | ".join(errores))
    return ""

def trocear(texto: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Divide el texto en fragmentos solapados para mejor contexto."""
    trozos = []
    for i in range(0, len(texto), chunk_size):
        # Fragmentación simple por tamaño para equilibrar contexto y coste.
        trozo = texto[i : i + chunk_size].strip()
        if trozo:
            trozos.append(trozo)
    return trozos

# ── Indexar documentos ─────────────────────────────────────────────────────────
docs_dir = Path(DOCS_DIR)
docs_dir.mkdir(exist_ok=True)

archivos = list(docs_dir.glob("*.txt")) + list(docs_dir.glob("*.pdf"))

if not archivos:
    print(f"\n⚠️  No se encontraron documentos en '{DOCS_DIR}'.")
    print("   Añade archivos .txt o .pdf y vuelve a ejecutar este script.\n")
else:
    total_fragmentos = 0
    for archivo in archivos:
        print(f"📄 Indexando: {archivo.name}")
        try:
            # Selecciona extractor según extensión para soportar txt y pdf en el mismo flujo.
            texto = cargar_pdf(archivo) if archivo.suffix == ".pdf" else cargar_txt(archivo)
            fragmentos = trocear(texto)
            if not fragmentos:
                print(f"   ⚠️  El archivo está vacío, se omite.")
                continue

            embeddings = embedder.encode(fragmentos).tolist()
            ids        = [f"{archivo.stem}_{i}" for i in range(len(fragmentos))]

            # Eliminar fragmentos anteriores del mismo archivo (para re-indexar)
            try:
                coleccion.delete(ids=ids)
            except Exception:
                # Si no existían ids previos, continuamos con alta normal.
                pass

            coleccion.add(documents=fragmentos, embeddings=embeddings, ids=ids)
            total_fragmentos += len(fragmentos)
            print(f"   ✅ {len(fragmentos)} fragmentos indexados")

        except Exception as e:
            print(f"   ❌ Error: {e}")

    print(f"\n✅ Indexación completa. Total: {coleccion.count()} fragmentos en la base de datos.")
