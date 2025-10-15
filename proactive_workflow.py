"""
Модуль для работы проактивных агентов (AGITATOR).
Отправляет сообщения при длительной неактивности пользователя.
"""

import time
import random
from env_loader import get_env
from error_handler import log_error
from logger import logger

INACTIVITY_N = int(get_env("INACTIVITY_N", 10))
RANDOM_MULTIPLIER_MIN = int(get_env("RANDOM_MULTIPLIER_MIN", 1))
RANDOM_MULTIPLIER_MAX = int(get_env("RANDOM_MULTIPLIER_MAX", 5))

class ProactiveWorkflow:
    """
    Класс для управления проактивными агентами.
    """

    def __init__(self, main_workflow, llm_subworkflow):
        self.main_workflow = main_workflow
        self.llm_subworkflow = llm_subworkflow
        self.active = True
        self.last_activity = time.time()
        self.next_trigger = self._calc_next_trigger()

    def _calc_next_trigger(self):
        multiplier = random.randint(INACTIVITY_N * RANDOM_MULTIPLIER_MIN, 
                                    INACTIVITY_N * RANDOM_MULTIPLIER_MAX)
        return self.last_activity + multiplier

    def update_activity(self):
        """Обновить время последней активности и пересчитать триггер."""
        self.last_activity = time.time()
        self.next_trigger = self._calc_next_trigger()

    def check_inactivity(self):
        """
        Проверяет неактивность и отправляет сообщение от AGITATOR через LLM.
        """
        try:
            if not self.active:
                return
            now = time.time()
            if now > self.next_trigger:
                prompt = "Пользователь давно не проявлял активности. Сгенерируй провокационное сообщение для чата."
                best_model = self.llm_subworkflow.get_best_model("AGITATOR")
                if best_model:
                    msg = self.llm_subworkflow.generate_response("AGITATOR", prompt)
                else:
                    msg = "В чате давно не было активности. AGITATOR отправляет сообщение!"
                logger.info(msg, "PROACTIVE")
                self.main_workflow.process_message("AGITATOR", msg)
                self.last_activity = now
                self.next_trigger = self._calc_next_trigger()
        except Exception as e:
            log_error(e, "ProactiveWorkflow.check_inactivity")
