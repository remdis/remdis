
![Color logo with background](https://github.com/remdis/remdis/assets/15374299/da5eb1c0-b3b4-4056-9c68-99448265e9a4)

# Remdis: Realtime Multimodal Dialogue System Toolkit
Remdisはテキスト・音声・マルチモーダル対話システム開発のためのプラットフォームです。
このページでは、Remdisを利用するための必要な情報を提供します。

## 特徴
- 非同期処理に基づくモジュールベースの対話システム
- Incremental Units (IU)を単位としたメッセージングとIncremental Modules (IM)による逐次処理
- Large Language Model (ChatGPT)の並列実行・ストリーミング生成による疑似的な逐次応答生成
- Voice Activity Projection (VAP)によるターンテイキング
- MMDAgent-EXとの連携によるエージェント対話
- Python実装、クロスプラットフォーム (Windows/MacOS/Ubuntu)
- マルチモーダル対応 (テキスト対話/音声対話)

![git_top_remdis](https://github.com/remdis/remdis/assets/15374299/dbc9deab-54b2-4b72-9ef9-06d6fcf38240)

---------------------------------------

## 更新履歴
- 2024/04/18 Windowsでconfig.yamlを開くときにエラーが出る問題を修正
- 2024/03/04 公開
---------------------------------------

## Remdisを用いたエージェント対話の例 (動画)

[![エージェント対話](https://img.youtube.com/vi/mYT7nC_U3M8/0.jpg)](https://www.youtube.com/embed/mYT7nC_U3M8?si=OO5eF-8kFCdtQwIx)

※動画では、ターンの取得に加えてAudio VAPの出力を使った相槌の判定も行っています。

---------------------------------------

## インストール方法
**注意) Windows環境で実施する場合、WSLはオーディオデバイスとの相性がよくないため、コマンドプロンプトの利用を推奨します。**
### Step 1. 事前準備
RemdisではRabbitMQの実行にDockerを利用します。Audio VAPでGPUを利用する場合はCUDA ToolkitとCuDNNのインストールが必要です。GPUなしでも実行可能ですが、リアルタイム性は若干低下します。

また、開発・実行にはAnacondaやMinicondaなどのPython環境を推奨します。ご自身の環境に合わせてインストールしてください。
- **Docker Desktopのインストール**
  - MacOS
    ~~~
    brew install --cask docker
    ~~~
  - Ubuntu
    - 最新のdebパッケージをDLし、インストール ([こちらのページ](https://docs.docker.jp/desktop/install/ubuntu.html)をご参照ください)
      ~~~
      sudo apt-get install ./docker-desktop-<version>-<arch>.deb
      ~~~
  - Windows
    - [Docker docs](https://docs.docker.com/desktop/install/windows-install/)からインストーラをダウンロードし、実行
- **(Optional) CUDA Toolkit/CuDNNのインストール**
  - Windows/Ubuntuは公式ドキュメントを参照し、インストールしてください。
  - Windowsでのインストールには下記手順でVisual C++のインストールが必要です。
    - [インストーラ](https://visualstudio.microsoft.com/ja/vs/community/)をダウンロードし、実行
    - 「C++ によるデスクトップ開発」にチェックを入れてインストールを実行
  
### Step 2. Remdis本体のインストール
- Clone
  ~~~
  git clone https://github.com/remdis/remdis.git
  ~~~
- Install
  ~~~
  cd remdis

  # 仮想環境での実行を推奨
  conda create -n remdis python=3.11
  conda activate remdis

  # 依存パッケージのインストール
  pip3 install -r requirements.txt
  ~~~

#### parallel-waveganのインストールでエラーが出る場合
- parallel-waveganをgitからクローンしてインストール
  ~~~
  git clone https://github.com/kan-bayashi/ParallelWaveGAN.git
  cd ParallelWaveGAN
  pip install -e .
  ~~~

### Step 3. 各種API鍵の取得と設定
- Google Speech Cloud APIのAPI鍵をJSON形式で取得し、config/config.yamlの下記部分にパスを記載
  ~~~
  ASR:
   ...
   json_key: <enter your API key>
  ~~~
- OpenAIのAPI鍵を取得し、config/config.yamlの下記部分に記載
  ~~~
  ChatGPT:
    api_key: <enter your API key>
  ~~~

### Step 4. VAPのインストール
- Clone
  ~~~
  git clone https://github.com/ErikEkstedt/VAP.git
  ~~~
- Install
  ~~~
  # pytorch, torchvision, torchaudioのインストール
  # torchは2.0.1以下 (= pyaudio 2.0.2)でのみ動作
  # インストールコマンドはOSによって若干異なる可能性あり
  pip3 install torch==2.0.1 torchvision torchaudio

  # 本体のインストール
  # Cloneしたディレクトリに移動し、下記を実行 
  pip3 install -r requirements.txt
  pip3 install -e .

  # Ekstedsらのrequirementsではtorchsummaryが不足しているため追加でインストール
  pip3 install torchsummary
  
  # モデルの解凍
  cd models/vap
  unzip sw2japanese_public0.zip
  ~~~

### Step 5. MMDAgent-EXのインストール (Windows 以外)
- Windows 以外のOSは、[MMDAgent-EX公式サイト](https://mmdagent-ex.dev/ja/)の[入手とビルド](https://mmdagent-ex.dev/ja/docs/build/) に従って MMDAgent-EX をインストール
- Windows はそのまま次へ（実行バイナリが同梱されているので手順不要）

---------------------------------------

## 利用方法
**注意) IMを実行する際は、個別のプロンプトで実施してください。例えば「3つのIMを起動」と書かれている場合は、まずプロンプトを3つ立ち上げ、それぞれのプロンプトで仮想環境をactivate、IM (Pythonプログラム)を実行という実施手順になります。**

### テキスト対話
- RabbitMQサーバを実行
  ~~~
  # Docker Desktopの場合はあらかじめアプリケーションを起動しておく必要あり
  docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.12-management
  ~~~
- 仮想環境をactivate
  ~~~
  conda activate remdis
  ~~~
- 3つのIMを起動
  ~~~
  python tin.py
  python dialogue.py
  python tout.py
  ~~~

### 音声対話
- RabbitMQサーバを実行
  ~~~
  # Docker Desktopの場合はあらかじめアプリケーションを起動しておく必要あり
  docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.12-management
  ~~~
- 仮想環境をactivate
  ~~~
  conda activate remdis
  ~~~
- 6つのIMを起動 (**システム発話が音声認識されないよう，ヘッドセットでの利用を推奨**)
  ~~~
  # 初回のみTTSでモデルの読み込みが入ります
  # audio_vap.pyまたはtext_vap.pyを動かさない場合は、ASR終端とTTS終端がターンの交代に用いられます
  python input.py
  python audio_vap.py or text_vap.py
  python asr.py
  python dialogue.py
  python tts.py
  python output.py
  ~~~

### MMDAgent-EXを用いたエージェント対話
- RabbitMQサーバを実行
  ~~~
  # Docker Desktopの場合はあらかじめアプリケーションを起動しておく必要あり
  docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.12-management
  ~~~
- 仮想環境をactivate
  ~~~
  conda activate remdis
  ~~~
- 5つのIMを起動　(**システム発話が音声認識されないよう，ヘッドセットでの利用を推奨**)
  ~~~
  python input.py
  python audio_vap.py or text_vap.py
  python asr.py
  python dialogue.py
  python tts.py
  ~~~
- MMDAgent-EXを起動
  - Windows: `MMDAgent-EX/run.vbs` を実行
  - WIndows 以外: MMDAgent-EX フォルダにある main.mdf を指定して MMDAgent-EX を実行
    ~~~
    cd MMDAgent-EX
    /somewhere/MMDAgent-EX/Release/MMDAgent-EX main.mdf
    ~~~
  
---------------------------------------

## TIPS
### マイクとスピーカーが正しく接続されているか確認したい
- chk_mic_spk.pyを実行
  ~~~
  # 自分の発話がフィードバックされて聴こえていればOK
  python input.py
  python chk_mic_spk.py
  python output.py
  ~~~

### Audio VAPの出力を可視化したい
- draw_vap_result.pyを実行
  ~~~
  # 音声対話の例
  python input.py
  python audio_vap.py
  python asr.py
  python dialogue.py
  python tts.py
  python output.py
  python draw_vap_result.py
  ~~~

### 一定時間が経過したらシステム側から話しかけるようにしたい
- time_out.pyを実行
  ~~~
  # テキスト対話の例
  python tin.py
  python dialogue.py
  python tout.py
  python time_out.py
  ~~~

---------------------------------------

## ライセンス
### ソースコードの利用規約
このレポジトリに含まれるオリジナルのファイルのライセンスは，models/vap以下に含まれる学習済みのVAPモデルを除き，Apache License 2.0です。商用・非商用問わずに、お使いいただけます。 
MMDAgent-EXに付属のCGアバターのライセンスについては MMDAgent-EX/asset/models/README-ja.txtをお読みください．
加えて，他のライセンスがすでに付与されているファイルはそのライセンスにも注意を払って利用してください。

~~~
Copyright 2024 Ryuichiro Higashinaka, Koh Mitsuda, Yuya Chiba, Akinobu Lee
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
~~~

### 学習済みVAPモデルの利用規約
Audio VAPのモデルは下記の対話データを用いて学習されています．
- [Switchboard-1 Release 2](https://catalog.ldc.upenn.edu/LDC97S62)
- [CALLHOME Japanese Speech](https://catalog.ldc.upenn.edu/LDC96S37)
- 旅行案内対話コーパス [稲葉+, 2021]
- 名古屋大学 東中研究室で収録された音声対話コーパス

学習済みのVAPモデルは、学術研究目的での利用のみ可能です。
それぞれのコーパスで利用規約が提供されている場合は併せてご確認ください。
また、作者は、学習済みモデルの利用による一切の請求、損害、その他の義務について何らの責任も負わないものとします。

### 外部パッケージの利用規約
Remdisでは、音声認識に[Google Cloud Speech-to-Text API](https://cloud.google.com/speech-to-text?hl=ja)、音声合成に[ttslearn](https://github.com/r9y9/ttslearn)、対話生成に[OpenAI API](https://openai.com/blog/openai-api)、ターンテイキングに[VAP](https://github.com/ErikEkstedt/VAP.git)といった外部パッケージを利用します。
ライセンスに関してはそれぞれのパッケージの利用規約をご参照ください。

---------------------------------------

## 論文
### Remdis
~~~
@inproceedings{remdis2024iwsds,
  title={The Remdis toolkit: Building advanced real-time multimodal dialogue systems with incremental processing and large language models},
  author={Chiba, Yuya and Mitsuda, Koh and Lee, Akinobu and Higashinaka, Ryuichiro},
  booktitle={Proc. IWSDS},
  pages={1--6},
  year={2024},
}
~~~
~~~
@inproceedings{remdis2023slud,
  title={Remdis: リアルタイムマルチモーダル対話システム構築ツールキット},
  author={千葉祐弥 and 光田航 and 李晃伸 and 東中竜一郎},
  booktitle={人工知能学会 言語・音声理解と対話処理研究会（第99回）},
  pages={25--30},
  year={2023},
}
~~~
### Audio VAP
~~~
@inproceedings{vap-sato2024slud,
  title={複数の日本語データセットによる音声活動予測モデルの学習とその評価},
  author={佐藤友紀 and 千葉祐弥 and 東中竜一郎},
  booktitle={人工知能学会 言語・音声理解と対話処理研究会（第100回）},
  pages={192--197},
  year={2024},
}
~~~
---------------------------------------

## 謝辞
本成果物は、JSTムーンショット型研究開発事業目標１「アバター共生社会プロジェクト」JPMJMS2011の支援を受けています。
