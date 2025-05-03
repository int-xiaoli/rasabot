from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from service.normalization import text_to_date
from service.weather import get_text_weather_date
from rasa_sdk.events import SlotSet
import requests

DEEPSEEK_API_KEY = "sk-e79979444e7b4f588881ed11f4d653ca"  # 需要用户替换真实API密钥
DEEPSEEK_ENDPOINT = "https://api.deepseek.com"

class CallDeepseekAction(Action):
    def name(self) -> Text:
        return "action_call_deepseek"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        try:
            # 增加重试机制和超时调整
            response = requests.post(
                f"{DEEPSEEK_ENDPOINT}/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={
                    "messages": [{
                        "role": "user",
                        "content": tracker.latest_message.get('text', '')
                    }],
                    "model": "deepseek-chat",
                    "temperature": 0.7
                },
                timeout=15  # 延长超时时间
            )
            response.raise_for_status()
            result = response.json()
            reply = result['choices'][0]['message']['content'].strip()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            if status_code == 429:
                reply = "请求过于频繁，请稍后再试"
            elif 500 <= status_code < 600:
                reply = "服务端暂时不可用，请稍后重试"
            else:
                reply = f"请求异常：{e.response.text}"
        except requests.exceptions.Timeout:
            reply = "请求超时，建议您检查网络连接后重试"
        except (ConnectionError, TooManyRedirects) as e:
            reply = "网络连接异常，请检查网络设置"
        except Exception as e:
            reply = f"服务暂时不可用：{str(e)}"
            logger.error(f"DeepSeek API Error: {str(e)}") 
        
        dispatcher.utter_message(text=reply)
        return []


class WeatherFormAction(Action):
    def name(self) -> Text:
        return "action_weather_form_submit"

    def run(
        self, dispatch: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict]:
        city = tracker.get_slot("address")
        date_text = tracker.get_slot("date-time")

        date_object = text_to_date(date_text)

        if not date_object:  # parse date_time failed
            msg = "暂不支持查询 {} 的天气".format([city, date_text])
            dispatch.utter_message(msg)
        else:
            try:
                weather_data = get_text_weather_date(city, date_object, date_text)
            except Exception as e:
                exec_msg = str(e)
                dispatch.utter_message(exec_msg)
            else:
                dispatch.utter_message(weather_data)

        return []  
    