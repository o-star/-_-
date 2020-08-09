from __future__ import division
import re
import sys

from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
import pyaudio
import parseModule as pm
from six.moves import queue

# Audio recording parameters
RATE = 44100
CHUNK = int(RATE / 10)  # 100ms


class MicrophoneStream(object):
    #Opens a recording stream as a generator yielding the audio chunks.

    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data

        self._buff = queue.Queue()
        self.closed = True


    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio

            # https://goo.gl/z757pE

            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,

            # Run the audio stream asynchronously to fill the buffer object.

            # This is necessary so that the input device's buffer doesn't

            # overflow while the calling thread makes network requests, etc.

            stream_callback=self._fill_buffer,

        )
        self.closed = False
        return self


    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True

        # Signal the generator to terminate so that the client's

        # streaming_recognize method will not block the process termination.

        self._buff.put(None)
        self._audio_interface.terminate()


    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        #Continuously collect data from the audio stream, into the buffer.

        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of

            # data, and stop iteration if the chunk is None, indicating the

            # end of the audio stream.

            chunk = self._buff.get()
            if chunk is None:
                return

            data = [chunk]

            # Now consume whatever other data's still buffered.

            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return

                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)


def listen_print_loop(responses):
    num_chars_printed = 0

    for response in responses:
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about

        # the first result being considered, since once it's `is_final`, it

        # moves on to considering the next utterance.

        result = response.results[0]

        if not result.alternatives:
            continue


        # Display the transcription of the top alternative.

        transcript = result.alternatives[0].transcript


        # Display interim results, but with a carriage return at the end of the

        # line, so subsequent lines will overwrite them.

        # If the previous result was longer than this one, we need to print

        # some extra spaces to overwrite the previous result

        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:
            #sys.stdout.write(transcript + overwrite_chars + '\r')
            #sys.stdout.flush()
            num_chars_printed = len(transcript)

        else:
            out = transcript + overwrite_chars
            return out


def main():

    # Language reference ==> http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.

    language_code = 'ko-KR'  # a BCP-47 language tag

    client = speech.SpeechClient()

    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code
    )

    streaming_config = types.StreamingRecognitionConfig(
        config=config,
        interim_results=True)

    texts = ""
    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (types.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)

        responses = client.streaming_recognize(streaming_config, requests)

        # Now, put the transcription responses to use.

        texts = listen_print_loop(responses) # type(output) == str

    with open("temp_res.txt", "w") as f:
        f.write(texts)
    keywords = pm.rankFunction(texts)
    pm.findInOut(keywords)  # 입/출항 추출 함수
    pm.findHarborLocation(keywords)  # 외/내항 추출 함수
    pm.findDate(keywords)  # 날짜 데이터 추출함수
    pm.findTime(keywords)  # 시간 데이터 추출함수
    pm.findShipName(keywords, texts)  # 선박명 추출함수
    pm.findShipWeight(keywords, texts)  # 총톤수 추출함수

    with open("result.txt", "w") as f:
        f.write(pm.answerDic[sys.argv[1]]+pm.answerDic[sys.argv[2]]+
                pm.answerDic[sys.argv[3]]+pm.answerDic[sys.argv[4]]+
                pm.answerDic[sys.argv[5]]+pm.answerDic[sys.argv[6]])

    print(pm.answerDic[sys.argv[1]], pm.answerDic[sys.argv[2]], pm.answerDic[sys.argv[3]], pm.answerDic[sys.argv[4]],
          pm.answerDic[sys.argv[5]], pm.answerDic[sys.argv[6]])


if __name__ == '__main__':
    main()

#58톤 선박명 창묵호 2020년 8월 9일 18시 28분에 울산 내항으로 출항할 예정이다

#이름은 효동호 무게는 132톤 2020년 8월 9일 23시 17분에 울산 외항으로 출항할 예정이다