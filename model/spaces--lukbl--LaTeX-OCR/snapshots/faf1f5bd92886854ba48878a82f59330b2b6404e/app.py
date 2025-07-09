import os
from PIL import Image
import streamlit
from pix2tex.cli import LatexOCR
from munch import Munch

args = Munch({'config': 'settings/config.yaml',
              'checkpoint': os.path.realpath(os.path.join(os.path.dirname(__file__), 'checkpoints/weights.pth')),
              'no_resize': False})
model = LatexOCR(args)

if __name__ == '__main__':
    streamlit.set_page_config(page_title='LaTeX-OCR')
    streamlit.title('LaTeX OCR')
    streamlit.markdown(
        'Convert images of equations to corresponding LaTeX code.\n\nThis is based on the `pix2tex` module. Check it out [![github](https://img.shields.io/badge/LaTeX--OCR-visit-a?style=social&logo=github)](https://github.com/lukas-blecher/LaTeX-OCR)')

    uploaded_file = streamlit.file_uploader(
        'Upload an image an equation',
        type=['png', 'jpg'],
    )

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        streamlit.image(image)
    else:
        streamlit.text('\n')

    if streamlit.button('Convert'):
        if uploaded_file is not None and image is not None:
            with streamlit.spinner('Computing'):
                try:
                    latex_code = model(image)
                    streamlit.code(latex_code, language='latex')
                    streamlit.markdown(f'$\\displaystyle {latex_code}$')
                except Exception as e:
                    streamlit.error(e)
        else:
            streamlit.error('Please upload an image.')
