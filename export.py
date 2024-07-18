# %%
import os
import shutil
import subprocess

# %%
SRC_ROOT = 'F:\\SteamLibrary\\steamapps\\common\\Pathfinder Second Adventure\\Wrath_Data\\StreamingAssets\\Audio\\GeneratedSoundBanks\\Windows'
SRC_DIR = os.path.join(SRC_ROOT, 'Packages')
SRC_INFO_PATH = os.path.join(SRC_ROOT, 'SoundbanksInfo.xml')
TMP_DIR = 'tmp'
BNK_DIR = 'bnk'
WEM_DIR = 'wem'
WAV_DIR = 'wav'
DEST_DIR = 'dest'

# %%
import xml.etree.ElementTree as ET
info = ET.parse(SRC_INFO_PATH).getroot()

# %%
# 台词和Event之间的映射关系（一对一）
import json
EVENT_MAP_FILE = 'F:\\SteamLibrary\\steamapps\\common\\Pathfinder Second Adventure\\Wrath_Data\\StreamingAssets\\Localization\\Sound.json'
with open(EVENT_MAP_FILE, 'r') as f:
    event_data = json.load(f)

# %%
# Event和音频文件之间的映射关系（可能一对多）
event_to_files = {}
for node in info.findall(".//Event"):
    event_name = node.get('Name')
    files = [os.path.basename(child.text) for child in node.findall('ReferencedStreamedFiles/File/ShortName')]
    if event_name in event_to_files: # 不同SoundBank间存在同名事件，但同名事件对应的文件应该都是一致的
        event_to_files[event_name] += files
    else:
        event_to_files[event_name] = files

# 所有与Sound.json有关联的音频文件名，可以过滤掉一些不知道用在哪里的音频
info_count = {}
for event in event_data['strings'].values():
    if event in event_to_files:
        for wav in event_to_files[event]:
            info_count[wav] = 0

skipped = {}

# %%
def run_command(command):
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")

# %%
def clean_or_create_dir(path: str):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

# %%
def unpack_wav(pck_name: str):
    pck_path = os.path.join(SRC_DIR, pck_name)
    if not os.path.isfile(pck_path):
        raise FileNotFoundError(pck_path)

    # 解包pck文件，包含bnk和wem文件
    print(f"Unpacking...", end="")
    clean_or_create_dir(TMP_DIR)
    run_command([
        "Tools/quickbms.exe",
        "-q",
        "-k",
        "Tools/wwise_pck_extractor.bms",
        pck_path,
        TMP_DIR
    ])
    bnk_list = [file for file in os.listdir(TMP_DIR) if file.endswith('.bnk')]
    wem_list = [file for file in os.listdir(TMP_DIR) if file.endswith('.wem')]
    print(f"\rUnpacked {len(bnk_list)} bnk files and {len(wem_list)} wem files from {pck_name}")
    clean_or_create_dir(WEM_DIR)
    for wem in wem_list:
        shutil.move(os.path.join(TMP_DIR, wem), os.path.join(WEM_DIR, wem))
    # bnk文件是另一种压缩包，里面的音频似乎用不上
    clean_or_create_dir(BNK_DIR)
    for bnk in bnk_list:
        shutil.move(os.path.join(TMP_DIR, bnk), os.path.join(BNK_DIR, bnk))

    wem_total = len(wem_list)
    if wem_total == 0:
        return
    wem_count = 0
    wem_skip_count = 0
    clean_or_create_dir(WAV_DIR)
    for wem in wem_list:
        wem_path = os.path.join(WEM_DIR, wem)
        wem_id = wem.replace('.wem', '')
        try:
            # 通过查找SoundbanksInfo.xml中的File节点，由wem文件的id获取文件名
            full_path = info.find(f".//StreamedFiles/File[@Id='{wem_id}']/ShortName").text
            wav_name = os.path.basename(full_path)
        except:
            wav_name = wem_id
        if wav_name in info_count:
            info_count[wav_name] += 1
            # 将wem转换为wav格式
            wav_path = os.path.join(WAV_DIR, wav_name)
            run_command([
                "Tools/vgmstream-cli.exe",
                "-o",
                wav_path,
                wem_path
            ])
        else:
            # 记录找不到关联的文件
            if wav_name not in skipped:
                skipped[wav_name] = 0
            skipped[wav_name] += 1
            wem_skip_count += 1
        wem_count += 1
        print(f"\rConvert wem to wav {wem_count}/{wem_total}, {wem_skip_count} skipped", end='')
    print('')

    # 由于GitHub库容量限制1GB，需要压缩文件大小，因此转为aac格式
    wav_list = os.listdir(WAV_DIR)
    wav_total = len(wav_list)
    if wav_total == 0:
        return
    wav_count = 0
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)
    for wav in wav_list:
        wav_path = os.path.join(WAV_DIR, wav)
        output_path = os.path.join(DEST_DIR, wav.replace('.wav', '.aac'))
        run_command([
            "Tools/ffmpeg.exe",
            "-loglevel",
            "error",
            "-y",
            "-i",
            wav_path,
            "-acodec",
            "aac",
            "-b:a",
            "96k",
            "-y",
            output_path
        ])
        wav_count += 1
        print(f"\rConvert wav to aac {wav_count}/{wav_total}", end='')
    print('')

# %%
clean_or_create_dir(DEST_DIR)
for file in os.listdir(SRC_DIR):
    if file.endswith('.pck'):
        unpack_wav(file)

# %%
with open('skipped.txt', 'w') as f: # 没有对应的Event
    for k, v in skipped.items():
        f.write(f"{v}: {k}\n")
with open('count.txt', 'w') as f: # 缺少文件或重复文件
    for k, v in info_count.items():
        if v != 1:
            f.write(f"{v}: {k}\n")

# %%
shutil.rmtree(TMP_DIR)
shutil.rmtree(BNK_DIR)
shutil.rmtree(WEM_DIR)
shutil.rmtree(WAV_DIR)


