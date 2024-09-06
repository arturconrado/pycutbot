import os
import time
import random
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from moviepy.editor import VideoFileClip
import yt_dlp as youtube_dl
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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


def buscar_videos(driver, query, max_results=5):
    logging.info(f"Iniciando a busca por vídeos com o tema: {query}...")
    driver.get("https://www.youtube.com")

    # Localiza a barra de busca e insere o termo
    search_box = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.NAME, 'search_query'))
    )

    # Simular digitação humana
    for char in query:
        search_box.send_keys(char)
        time.sleep(random.uniform(0.1, 0.3))  # Pausa aleatória entre as teclas

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
        except Exception as e:
            logging.error(f"Erro ao coletar informações do vídeo: {e}")
            title, url, views = "Desconhecido", "Desconhecido", "Desconhecido"

        logging.info(f"Encontrado vídeo: {title} - URL: {url} - Visualizações: {views}")

        videos.append({
            'title': title,
            'url': url,
            'views': views
        })

    return videos


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


def verificar_duracao(video_file):
    clip = VideoFileClip(video_file)
    duration = clip.duration
    clip.close()  # Fechar o clip após a verificação
    return duration


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

    while start_time < duration:
        end_time = min(start_time + corte_duration, duration)
        corte_video = os.path.join(output_dir, f"corte_{int(start_time)}_{video_title}.mp4")
        clip = VideoFileClip(video_file).subclip(start_time, end_time)
        clip.write_videofile(corte_video, codec="libx264", audio_codec="aac")
        clip.close()  # Fechar o clip após o corte
        cortes.append(corte_video)
        start_time += corte_duration

    return cortes


# Interface no Terminal
def interface_terminal():
    query = input("Digite o tema para pesquisar vídeos: ")
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
        print(f"   URL: {video['url']}\n")

    # Download e corte dos vídeos
    for video in videos:
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
                print(f"O vídeo {video['title']} tem menos de 1 minuto e foi ignorado.")
        except FileNotFoundError as e:
            print(f"Erro ao processar o vídeo {video['title']}: {e}")

if __name__ == "__main__":
    interface_terminal()
