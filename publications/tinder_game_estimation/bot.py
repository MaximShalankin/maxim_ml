import os
import math
import json
import time
import random
import logging
import threading
from dataclasses import dataclass, field
from typing import Tuple, List, Dict
from collections import defaultdict
from functools import cached_property
import telebot
from telebot import types


# Configuration
class Config:
    TOKEN_ENV_VAR = 'TOKEN_ENV_VAR'  # в этой переменной окружения ваш токен бота
    IMAGES_DIR = 'images'  # по этому пути лежат папки с изображениями
    NUM_CATEGORIES = 5
    MAX_RATINGS = 40
    SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif')
    SESSION_TIMEOUT = 54000  # seconds (86400 - 24 hours) - после этого времени попытки юзера обнулятся
    STATS_FILE = 'image_stats.json'  # output статистика показов
    STATS_SAVE_INTERVAL = 300  # save stats every n seconds


session_lock = threading.RLock()
stats_lock = threading.RLock()


@dataclass
class UserSession:
    chat_id: int
    ratings_count: int = 0
    current_media_ids: List[int] = field(default_factory=list)
    last_activity: float = field(default_factory=time.time)
    current_comparison: Dict = field(default_factory=dict)
    choice_made: bool = False  # Flag to track if user has made a choice for current comparison
    last_shown_pair: Dict = field(default_factory=dict)  # Store the last shown pair

    @property
    def is_completed(self) -> bool:
        return self.ratings_count >= Config.MAX_RATINGS

    def update_activity(self):
        self.last_activity = time.time()


class ImageStats:
    def __init__(self, stats_file):
        self.stats_file = stats_file
        self.category_stats = defaultdict(lambda: defaultdict(int))
        self.load_stats()

    def load_stats(self):
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    for category, images in data.items():
                        for image, count in images.items():
                            self.category_stats[category][image] = count
        except Exception as e:
            logging.error(f"Failed to load stats: {e}")

    def save_stats(self):
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.category_stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to save stats: {e}")

    def increment_view(self, category, image_name):
        with stats_lock:
            self.category_stats[str(category)][image_name] += 1

    def get_view_count(self, category, image_name):
        return self.category_stats.get(str(category), {}).get(image_name, 0)


class LoggingManager:
    def __init__(self, base_logger):
        self.base_logger = base_logger
        self.user_loggers = {}

    def _get_log_path(self, chat_id: int) -> str:
        log_dir = os.path.join('logs', str(chat_id))
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, 'ratings.log')

    def get_user_logger(self, chat_id: int) -> logging.Logger:
        if chat_id in self.user_loggers:
            return self.user_loggers[chat_id]

        log_file = self._get_log_path(chat_id)
        logger_name = f"user_{chat_id}"
        user_logger = logging.getLogger(logger_name)

        # Clear existing handlers
        if user_logger.handlers:
            for handler in user_logger.handlers[:]:
                user_logger.removeHandler(handler)

        try:
            file_handler = logging.FileHandler(log_file, mode='a')
            formatter = logging.Formatter('%(message)s')
            file_handler.setFormatter(formatter)
            user_logger.addHandler(file_handler)
            user_logger.setLevel(logging.INFO)
            user_logger.propagate = False
            self.user_loggers[chat_id] = user_logger
        except Exception as e:
            self.base_logger.error(f"Failed to set up logging for user {chat_id}: {e}")

        return user_logger

    def log_comparison(self, chat_id: int, category: int, img1: str, img2: str, action: str):
        logger = self.get_user_logger(chat_id)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"{timestamp}, {category}, {img1}, {img2}, {action}"
        logger.info(log_message)
        return timestamp


class ImageComparisonBot:
    def __init__(self):
        self.config = Config()
        token = os.environ.get(self.config.TOKEN_ENV_VAR)
        if not token or token.strip() == "":
            raise ValueError(f"Missing or empty {self.config.TOKEN_ENV_VAR} environment variable")

        self.bot = telebot.TeleBot(token, threaded=True)
        self.user_sessions = {}
        self.stats = ImageStats(self.config.STATS_FILE)
        self._pair_history = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('image_comparison_bot')
        self.logging_manager = LoggingManager(self.logger)

        # Create images directory if needed
        os.makedirs(self.config.IMAGES_DIR, exist_ok=True)

        self._register_handlers()

    def _register_handlers(self):
        self.bot.message_handler(commands=['start'])(self.handle_start)
        self.bot.message_handler(commands=['help'])(self.handle_help)
        self.bot.message_handler(commands=['status'])(self.handle_status)
        self.bot.message_handler(func=lambda message: True)(self.handle_message)
        self.bot.callback_query_handler(func=lambda call: call.data.startswith('choose:'))(
            self.handle_image_choice)

    def get_user_session(self, chat_id: int) -> UserSession:
        with session_lock:
            if chat_id not in self.user_sessions:
                self.user_sessions[chat_id] = UserSession(chat_id)

            # Update last activity time
            self.user_sessions[chat_id].update_activity()
            return self.user_sessions[chat_id]

    @cached_property
    def category_images(self):
        """Lazily load images from all categories"""
        images_by_category = {}
        for category in range(1, self.config.NUM_CATEGORIES + 1):
            category_path = os.path.join(self.config.IMAGES_DIR, str(category))
            os.makedirs(category_path, exist_ok=True)

            images = [
                img for img in os.listdir(category_path)
                if os.path.isfile(os.path.join(category_path, img)) and
                   img.lower().endswith(self.config.SUPPORTED_EXTENSIONS)
            ]

            images_by_category[category] = images

            # Initialize stats for any new images
            for img in images:
                if img not in self.stats.category_stats.get(str(category), {}):
                    self.stats.category_stats[str(category)][img] = 0

        return images_by_category

    def update_pair_history(self, category: int, img1: str, img2: str):
        """Update the pairing history when a new pair is shown"""
        # Increment count for both directions of the pair
        self._pair_history[category][img1][img2] += 1
        self._pair_history[category][img2][img1] += 1

    def get_weighted_image_pair(self, category: int) -> Tuple[str, str]:
        """Get a pair of images with improved weighting strategy for better distribution."""
        # Force refresh of cached property if needed
        if not hasattr(self, '_category_images_cache'):
            self._category_images_cache = self.category_images

        images = self._category_images_cache.get(category, [])

        if len(images) < 2:
            self.logger.warning(f"Not enough images in category {category}. Found: {len(images)}")
            raise ValueError(f"Not enough images in category {category}. Found: {len(images)}")

        # Get view counts and calculate weights
        view_counts = {img: self.stats.get_view_count(category, img) for img in images}

        # Find min and max view counts for normalization
        min_views = min(view_counts.values()) if view_counts else 0
        max_views = max(view_counts.values()) if view_counts else 1

        # Calculate weights using sigmoid-like function
        weights = {}
        for img, count in view_counts.items():
            # Normalize count to range [0,1]
            if max_views > min_views:
                normalized_count = (count - min_views) / (max_views - min_views)
            else:
                normalized_count = 0

            # Apply inverse sigmoid-like weighting (higher weight for less viewed images)
            weight = 1.0 / (1.0 + math.exp(5 * normalized_count - 2.5))
            weights[img] = weight

        # Normalize weights to sum to 1
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {img: w / total_weight for img, w in weights.items()}
        else:
            weights = {img: 1.0 / len(images) for img in images}

        # Select first image based on weights
        img1 = random.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]

        # Remove the first image from the pool
        remaining_images = [img for img in images if img != img1]

        # For the second image, prioritize images that haven't been paired with img1 recently
        pair_history = self._pair_history[category][img1]

        # Adjust weights based on pairing history
        remaining_weights = {}
        for img in remaining_images:
            base_weight = weights.get(img, 1.0 / len(remaining_images))
            # Reduce weight if this pair was shown recently
            pair_count = pair_history.get(img, 0)
            history_factor = math.exp(-0.5 * pair_count)  # Exponential decay based on pair frequency
            remaining_weights[img] = base_weight * history_factor

        # Normalize remaining weights
        total_remaining = sum(remaining_weights.values())
        if total_remaining > 0:
            remaining_weights = {img: w / total_remaining for img, w in remaining_weights.items()}
        else:
            remaining_weights = {img: 1.0 / len(remaining_images) for img in remaining_images}

        # Select second image
        img2 = random.choices(
            list(remaining_weights.keys()),
            weights=list(remaining_weights.values()),
            k=1
        )[0]

        # Update pair history
        self.update_pair_history(category, img1, img2)

        return img1, img2

    def create_comparison_keyboard(self, category: int) -> types.InlineKeyboardMarkup:
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton("Первая", callback_data=f"choose:{category}:left")
        btn2 = types.InlineKeyboardButton("Вторая", callback_data=f"choose:{category}:right")
        keyboard.add(btn1, btn2)
        return keyboard

    def clean_previous_messages(self, chat_id: int) -> None:
        session = self.get_user_session(chat_id)
        if not session.current_media_ids:
            return

        for msg_id in session.current_media_ids:
            try:
                self.bot.delete_message(chat_id, msg_id)
            except Exception as e:
                if "message to delete not found" in str(e).lower():
                    self.logger.debug(f"Message {msg_id} already deleted")
                elif "message can't be deleted" in str(e).lower():
                    self.logger.warning(f"No permission to delete message {msg_id}")
                else:
                    self.logger.error(f"Error deleting message {msg_id}: {e}")

        # Clear the list even if deletion fails
        session = self.get_user_session(chat_id)
        session.current_media_ids = []

    def send_image_comparison(self, chat_id: int, category: int) -> bool:
        session = self.get_user_session(chat_id)
        self.clean_previous_messages(chat_id)

        try:
            # Create category directory if needed
            category_path = os.path.join(self.config.IMAGES_DIR, str(category))
            os.makedirs(category_path, exist_ok=True)

            # Check if there's an unanswered comparison
            if not session.choice_made and session.last_shown_pair and 'category' in session.last_shown_pair:
                # Use the last shown pair instead of generating a new one
                img1 = session.last_shown_pair['img1']
                img2 = session.last_shown_pair['img2']
                category = session.last_shown_pair['category']

            else:
                # Generate a new weighted pair
                img1, img2 = self.get_weighted_image_pair(category)

                # Update view statistics for both images
                self.stats.increment_view(category, img1)
                self.stats.increment_view(category, img2)

            img1_path = os.path.join(self.config.IMAGES_DIR, str(category), img1)
            img2_path = os.path.join(self.config.IMAGES_DIR, str(category), img2)

            # Store current comparison info in session
            session.current_comparison = {
                'category': category,
                'img1': img1,
                'img2': img2,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }

            # Update last_shown_pair with current comparison
            session.last_shown_pair = session.current_comparison.copy()

            # Reset choice_made flag when showing comparison
            session.choice_made = False

            # Log what the user is seeing
            self.logging_manager.log_comparison(chat_id, category, img1, img2, "SHOWN")

            # Send images
            with open(img1_path, 'rb') as file1, open(img2_path, 'rb') as file2:
                media = [types.InputMediaPhoto(file1), types.InputMediaPhoto(file2)]
                sent_media = self.bot.send_media_group(chat_id, media)
                prompt = self.bot.send_message(
                    chat_id,
                    f"Какое изображение лучше? (ваш прогресс {session.ratings_count}/{self.config.MAX_RATINGS})",
                    reply_markup=self.create_comparison_keyboard(category)
                )

                session.current_media_ids = [m.message_id for m in sent_media] + [prompt.message_id]
                return True

        except Exception as e:
            self.logger.error(f"Error sending image comparison: {e}")
            self.bot.send_message(chat_id, "⚠️ Произошла ошибка при загрузке изображений.")
            return False

    def get_next_category(self, user: UserSession) -> int:
        return ((user.ratings_count) % self.config.NUM_CATEGORIES) + 1

    def handle_start(self, message):
        chat_id = message.chat.id
        session = self.get_user_session(chat_id)

        if session.is_completed:
            self.bot.send_message(
                chat_id,
                "🎉 Вы оценили весь доступный лимит! Спасибо за участие! (лимит обнулится через 1 день неактивности)"
            )
            return

        self.bot.send_message(
            chat_id,
            f"👋 Добро пожаловать! Выберите, какое изображение вам нравится больше."
        )
        category = self.get_next_category(session)
        self.send_image_comparison(chat_id, category)

    def handle_help(self, message):
        chat_id = message.chat.id
        self.bot.send_message(chat_id, "ℹ️ Выберите, какое из двух изображений вам нравится больше.")

    def handle_status(self, message):
        chat_id = message.chat.id
        session = self.get_user_session(chat_id)

        if session.is_completed:
            self.bot.send_message(
                chat_id,
                "🎉 Вы оценили весь доступный лимит! Спасибо за участие! (лимит обнулится через 1 день неактивности)"
            )
        else:
            remaining = self.config.MAX_RATINGS - session.ratings_count
            self.bot.send_message(
                chat_id,
                f"📊 Ваш прогресс: {session.ratings_count}/{self.config.MAX_RATINGS}. осталось попыток: {remaining}."
            )

    def handle_message(self, message):
        chat_id = message.chat.id
        session = self.get_user_session(chat_id)

        if session.is_completed:
            self.bot.send_message(
                chat_id,
                "🎉 Вы оценили весь доступный лимит! Спасибо за участие! (лимит обнулится через 1 день неактивности)"
            )
            return

        if not session.current_media_ids:
            category = self.get_next_category(session)
            self.send_image_comparison(chat_id, category)
        else:
            self.bot.send_message(chat_id, "⚠️ Пожалуйста, сделайте выбор для текущей пары изображений.")

    def handle_image_choice(self, call):
        chat_id = call.message.chat.id
        session = self.get_user_session(chat_id)

        if session.is_completed:
            self.bot.answer_callback_query(call.id, "Вы уже завершили все оценки!", cache_time=60)
            return

        # Check if user already made a choice for this comparison
        if session.choice_made:
            self.bot.answer_callback_query(
                call.id,
                "Ваш выбор уже принят, подождите следующую пару изображений.",
                cache_time=60
            )
            return

        try:
            parts = call.data.split(':')
            if len(parts) != 3 or parts[0] != "choose":
                raise ValueError(f"Invalid callback data format: {call.data}")

            _, category_str, choice = parts

            if not category_str.isdigit() or choice not in ["left", "right"]:
                raise ValueError(f"Invalid callback data values: {call.data}")

            category = int(category_str)

            # Use a lock to prevent race conditions
            with session_lock:
                session = self.get_user_session(chat_id)
                # Mark that user has made a choice for current comparison
                session.choice_made = True

                # Clear the last_shown_pair since user has made a choice
                session.last_shown_pair = {}

                # Increment ratings count
                session.ratings_count += 1

            # Log the choice using consistent format
            timestamp = session.current_comparison.get('timestamp', time.strftime("%Y-%m-%d %H:%M:%S"))
            self.logging_manager.log_comparison(chat_id, category,
                                                session.current_comparison.get('img1', ''),
                                                session.current_comparison.get('img2', ''),
                                                f"CHOSEN_{choice.upper()}")

            self.clean_previous_messages(chat_id)

            self.bot.answer_callback_query(
                call.id,
                # f"✅ Выбор принят! {session.ratings_count}/{self.config.MAX_RATINGS}",
                # show_alert=True,
                cache_time=60
            )

            if session.is_completed:
                self.bot.send_message(
                    chat_id,
                    "🎉 Вы оценили весь доступный лимит! Спасибо за участие! (лимит обнулится через 1 день неактивности)"
                )
            else:
                next_category = self.get_next_category(session)
                self.send_image_comparison(chat_id, next_category)

        except Exception as e:
            self.logger.error(f"Error in handle_image_choice: {e}")
            self.bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте еще раз.", cache_time=60)

    def _cleanup_sessions(self):
        """Periodically clean up inactive sessions"""
        while True:
            try:
                current_time = time.time()
                with session_lock:
                    to_remove = []
                    for chat_id, session in self.user_sessions.items():
                        if current_time - session.last_activity > self.config.SESSION_TIMEOUT:
                            to_remove.append(chat_id)

                    for chat_id in to_remove:
                        del self.user_sessions[chat_id]
                        self.logger.info(f"Cleaned up inactive session for chat_id {chat_id}")

                time.sleep(300)  # Check every 5 minutes
            except Exception as e:
                self.logger.error(f"Error in session cleanup: {e}")
                time.sleep(60)  # Retry after a minute if there was an error

    def _save_stats_periodically(self):
        """Periodically save statistics to disk"""
        while True:
            try:
                self.stats.save_stats()
                self.logger.info("Statistics saved to disk")
                time.sleep(self.config.STATS_SAVE_INTERVAL)
            except Exception as e:
                self.logger.error(f"Error saving statistics: {e}")
                time.sleep(60)  # Retry after a minute if there was an error

    def start_polling(self):
        self.logger.info("Bot started")

        # Scan all images to initialize statistics
        self.category_images  # Access cached property to initialize

        # Start session cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_sessions, daemon=True)
        cleanup_thread.start()

        # Start stats saving thread
        stats_thread = threading.Thread(target=self._save_stats_periodically, daemon=True)
        stats_thread.start()

        self.bot.polling(none_stop=True)


def main():
    try:
        bot = ImageComparisonBot()
        bot.start_polling()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
        # Save stats one last time before exiting
        bot.stats.save_stats()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    main()
