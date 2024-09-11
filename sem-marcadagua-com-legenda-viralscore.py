import logging
import os
import random
import time

import cv2
import numpy as np
import pytesseract
import yt_dlp as youtube_dl
from moviepy.editor import VideoFileClip, TextClip, concatenate_videoclips, vfx
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Configurar logs
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# Configuração do WebDriver (Chrome)
def configurar_driver():
    options = Options()
    options.add_argument('--headless')  # Executar o Chrome em modo headless
    service = Service(ChromeDriverManager().install())  # Usa o webdriver_manager para gerenciar o driver
    driver = webdriver.Chrome(service=service, options=options)
    return driver


# Função para verificar marca d'água em thumbnails (imagens de prévia do vídeo)
def verificar_marca_dagua_thumbnail(thumbnail_url):
    try:
        # Baixa a thumbnail para verificação
        thumbnail_filename = 'thumbnail.jpg'
        os.system(f"curl {thumbnail_url} -o {thumbnail_filename}")

        # Processa a imagem para detectar marca d'água usando Tesseract
        image = cv2.imread(thumbnail_filename)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray)

        # Verifica se o OCR detectou texto (possível marca d'água)
        if text.strip():
            logging.info(f"Marca d'água detectada na thumbnail: {thumbnail_url}")
            return True
        else:
            logging.info(f"Nenhuma marca d'água detectada na thumbnail: {thumbnail_url}")
            return False

    except Exception as e:
        logging.error(f"Erro ao verificar a marca d'água: {e}")
        return False


# Função para buscar vídeos do YouTube
def buscar_videos(driver, query, max_results=5):
    logging.info(f"Iniciando a busca por vídeos com o tema: {query}...")
    driver.get("https://www.youtube.com")

    # Localiza a barra de busca e insere o termo
    search_box = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.NAME, 'search_query'))
    )
    search_box.send_keys(query)
    search_box.send_keys(Keys.RETURN)
    time.sleep(random.uniform(2, 5))  # Pausa para aguardar o carregamento dos resultados

    # Aguarde até que os vídeos estejam disponíveis
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'ytd-video-renderer'))
        )
    except Exception as e:
        logging.error(f"Erro ao aguardar a presença dos vídeos: {e}")
        return []

    videos = []
    logging.info("Procurando elementos de vídeo na página...")

    # Procura os elementos de vídeo na página
    video_elements = driver.find_elements(By.CSS_SELECTOR, 'ytd-video-renderer')

    if not video_elements:
        logging.warning("Nenhum elemento de vídeo encontrado na página de resultados.")
        return []

    for video in video_elements[:max_results]:
        try:
            title = video.find_element(By.CSS_SELECTOR, 'a#video-title').get_attribute('title')
            url = video.find_element(By.CSS_SELECTOR, 'a#video-title').get_attribute('href')
            views = video.find_element(By.CSS_SELECTOR, 'span.style-scope.ytd-video-meta-block').text
            thumbnail_url = video.find_element(By.CSS_SELECTOR, 'img').get_attribute('src')

            # Obtenha métricas adicionais para o Viral Score
            likes = int(video.find_element(By.CSS_SELECTOR, 'span#text').text.replace(',', '').replace(' likes', ''))
            dislikes = int(
                video.find_element(By.CSS_SELECTOR, 'span#text').text.replace(',', '').replace(' dislikes', ''))
            comments = int(
                video.find_element(By.CSS_SELECTOR, 'span#text').text.replace(',', '').replace(' comments', ''))
            shares = 0  # YouTube não fornece dados de compartilhamento diretamente; pode ser estimado se disponível

            viral_score = calcular_viral_score(
                int(views.replace(',', '')),
                likes,
                dislikes,
                comments,
                shares
            )

            logging.info(f"Vídeo '{title}' - Viral Score: {viral_score:.2f}")

        except Exception as e:
            logging.error(f"Erro ao coletar informações do vídeo: {e}")
            title, url, views, thumbnail_url = "Desconhecido", "Desconhecido", "Desconhecido", None

        videos.append({
            'title': title,
            'url': url,
            'views': views,
            'viral_score': viral_score
        })

    # Ordena vídeos pelo Viral Score em ordem decrescente
    videos = sorted(videos, key=lambda x: x['viral_score'], reverse=True)
    return videos


# Função para baixar o vídeo
def baixar_video(video_url, video_title):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': f'{video_title}.%(ext)s',
        'prefer_ffmpeg': True,
        'noplaylist': True,
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    # Verifique os arquivos baixados e retorne o nome do arquivo principal
    files = os.listdir()
    video_file = None
    for file in files:
        if file.startswith(video_title) and file.endswith(('.mp4', '.webm')):
            video_file = file
            break

    if not video_file:
        raise FileNotFoundError("Arquivo de vídeo não encontrado após o download.")

    return video_file


# Verifica a duração do vídeo
def verificar_duracao(video_file):
    clip = VideoFileClip(video_file)
    duration = clip.duration
    clip.close()  # Fechar o clip após a verificação
    return duration


# Função para calcular o Viral Score
def calcular_viral_score(visualizacoes, curtidas, descurtidas, comentarios, compartilhamentos):
    # Exemplo simplificado de fórmula
    try:
        score = (
                (np.log1p(visualizacoes) * 0.4) +
                (np.log1p(curtidas) * 0.3) -
                (np.log1p(descurtidas) * 0.1) +
                (np.log1p(comentarios) * 0.15) +
                (np.log1p(compartilhamentos) * 0.05)
        )
        return score
    except Exception as e:
        logging.error(f"Erro ao calcular o Viral Score: {e}")
        return 0


# Adiciona legendas animadas ao vídeo
def adicionar_legendas(video_file, legendas):
    clip = VideoFileClip(video_file)
    clips = [clip]

    for i, (texto, tempo_inicio, tempo_fim) in enumerate(legendas):
        txt_clip = TextClip(texto, fontsize=40, color='white', bg_color='black', size=clip.size)
        txt_clip = txt_clip.set_position('center').set_duration(tempo_fim - tempo_inicio).set_start(tempo_inicio)
        clips.append(txt_clip)

    video_com_legendas = concatenate_videoclips(clips, method="compose")
    output_file = video_file.replace(".mp4", "_com_legendas.mp4")
    video_com_legendas.write_videofile(output_file, codec="libx264", audio_codec="aac")
    return output_file


# Ajusta o vídeo para formato 9:16
def ajustar_formato_9_16(video_file):
    clip = VideoFileClip(video_file)
    largura, altura = clip.size
    nova_largura = int(altura * 9 / 16)

    # Redimensiona o vídeo para garantir que o vídeo tenha a proporção 9:16
    if largura < nova_largura:
        clip = clip.resize(width=nova_largura)

    # Adiciona barras laterais para garantir a proporção 9:16
    if largura > nova_largura:
        clip = clip.fx(vfx.crop, x1=(largura - nova_largura) // 2, width=nova_largura, height=altura)

    output_file = video_file.replace(".mp4", "_ajustado_9_16.mp4")
    clip.write_videofile(output_file, codec="libx264", audio_codec="aac")
    return output_file


# Função para cortar o vídeo em segmentos e adicionar legendas
def cortar_video_segmentos(video_file, video_title):
    duration = verificar_duracao(video_file)

    # Verifique se o vídeo tem duração suficiente
    if duration < 60:
        logging.error(f"O vídeo {video_title} tem menos de 1 minuto e não pode ser cortado.")
        return []

    min_corte_duration = 60  # Duração mínima de cada corte em segundos
    num_cortes = int(duration // min_corte_duration)  # Calcula o número de cortes
    if num_cortes == 0:
        num_cortes = 1  # Garantir pelo menos um corte

    corte_duration = duration / num_cortes
    start_time = 0
    cortes = []

    # Cria a pasta para armazenar os cortes
    output_dir = video_title
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Exemplo de legendas (texto, tempo_inicio, tempo_fim)
    legendas = [
        ("Bem-vindo ao vídeo!", 0, 5),
        ("Vamos aprender algo novo!", 5, 10)
    ]

    while start_time < duration:
        end_time = min(start_time + corte_duration, duration)
        corte_video = os.path.join(output_dir, f"corte_{int(start_time)}s_{int(end_time)}s.mp4")

        clip = VideoFileClip(video_file).subclip(start_time, end_time)
        clip = ajustar_formato_9_16(clip.filename)  # Ajusta o formato do vídeo

        # Adiciona legendas ao corte
        corte_com_legendas = adicionar_legendas(corte_video, legendas)
        os.rename(corte_com_legendas, corte_video)  # Substitui o arquivo de corte

        cortes.append(corte_video)
        start_time += corte_duration

    return cortes


def interface_terminal():
    query = input("Digite o tema para buscar vídeos: ")
    max_results = int(input("Quantos vídeos deseja buscar? "))

    driver = configurar_driver()
    videos = buscar_videos(driver, query, max_results)
    driver.quit()

    if not videos:
        print("Nenhum vídeo encontrado.")
        return

    print(f"\nForam encontrados {len(videos)} vídeos sobre '{query}':\n")
    for i, video in enumerate(videos, 1):
        print(f"{i}. Título: {video['title']}")
        print(f"   Visualizações: {video['views']}")
        print(f"   Viral Score: {video['viral_score']:.2f}")
        print(f"   URL: {video['url']}\n")

    # Permitir que o usuário escolha o número de vídeos a serem processados
    num_videos_para_processar = int(input("Quantos vídeos deseja processar? "))
    if num_videos_para_processar > len(videos):
        print(
            "Número de vídeos solicitado excede o número de vídeos encontrados. Processando todos os vídeos encontrados.")
        num_videos_para_processar = len(videos)

    videos_para_processar = videos[:num_videos_para_processar]

    # Download e corte dos vídeos
    for video in videos_para_processar:
        print(f"Baixando vídeo: {video['title']}")
        try:
            video_file = baixar_video(video['url'], video['title'])
            print(f"Verificando duração do vídeo...")
            duration = verificar_duracao(video_file)
            if duration >= 60:  # Verificar se a duração é pelo menos 1 minuto
                print(f"Cortando vídeo em segmentos de pelo menos 1 minuto: {video['title']}")
                cortes = cortar_video_segmentos(video_file, video['title'])
                print(f"Vídeo {video['title']} cortado.")
                print(f"Arquivos de cortes gerados: {cortes}")
            else:
                print(f"O vídeo {video['title']} tem menos de 1 minuto e não será cortado.")
        except Exception as e:
            print(f"Erro ao processar o vídeo {video['title']}: {e}")


# Executa o script principal
if __name__ == "__main__":
    interface_terminal()
