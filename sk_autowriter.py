import os
import time
import logging
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError, AuthenticationError
from threading import Semaphore


# ============================================================
# 加载.env
# ============================================================
load_dotenv()

# ============================================================
# 配置化参数（支持 .env 覆盖）
# ============================================================
# API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise EnvironmentError("❌ DEEPSEEK_API_KEY 未配置，请检查.env文件")

# LLM 参数
LLM_MODEL = os.getenv("LLM_MODEL", "MiniMax-M2.7")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4000"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60.0"))  # API 超时(秒)
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))  # 最大重试次数
LLM_RETRY_DELAY = float(os.getenv("LLM_RETRY_DELAY", "1.0"))  # 初始重试延迟(秒)

# 并发控制
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "3"))

# 代理配置（默认不禁用代理）
DISABLE_PROXY = os.getenv("DISABLE_PROXY", "false").lower() == "true"

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "agent3a_article.md")
WATCH_FOLDER = os.getenv("WATCH_FOLDER") or os.path.join(BASE_DIR, "cases", "2026")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER") or os.path.join(BASE_DIR, "articles", "2026")

# ============================================================
# 配置日志
# ============================================================
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, 'autowriter.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# 代理环境变量处理（可选禁用）
# ============================================================
if DISABLE_PROXY:
    for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
        if proxy_var in os.environ:
            del os.environ[proxy_var]
    logger.info("✅ 代理环境变量已禁用")
else:
    logger.info("✅ 保留系统代理配置")

# ============================================================
# OpenAI 客户端初始化
# ============================================================
try:
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com/anthropic",
        http_client=None,
        timeout=LLM_TIMEOUT
    )
    logger.info("✅ OpenAI客户端初始化成功")
except Exception as e:
    logger.error(f"❌ 客户端初始化失败: {str(e)}")
    raise

# ============================================================
# 路径验证与创建
# ============================================================
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(WATCH_FOLDER, exist_ok=True)

# ============================================================
# 读取提示词（带异常处理）
# ============================================================
SYSTEM_PROMPT = ""
try:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
    logger.info(f"✅ 提示词加载成功，长度: {len(SYSTEM_PROMPT)} 字符")
except FileNotFoundError:
    logger.error(f"❌ 提示词文件不存在: {PROMPT_PATH}")
    raise
except Exception as e:
    logger.error(f"❌ 读取提示词失败: {str(e)}")
    raise

# ============================================================
# 工具函数
# ============================================================
def wait_file_stable(file_path, check_interval=0.1, stable_times=3, max_wait=5.0):
    """等待文件大小稳定（连续N次检查大小一致）"""
    last_size = -1
    stable_count = 0
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            current_size = os.path.getsize(file_path)
            if current_size == last_size:
                stable_count += 1
                if stable_count >= stable_times:
                    return True
            else:
                last_size = current_size
                stable_count = 0
            time.sleep(check_interval)
        except Exception:
            time.sleep(check_interval)
    
    logger.warning(f"⚠️ 文件 {file_path} 写入超时")
    return False

def read_file_with_encoding_fallback(file_path):
    """智能读取文件，支持多种编码"""
    # 优先尝试 UTF-8
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5']
    
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            if encoding != 'utf-8':
                logger.info(f"📝 文件 {os.path.basename(file_path)} 使用 {encoding} 编码读取")
            return content
        except (UnicodeDecodeError, LookupError):
            continue
    
    # 最后的手段：使用 chardet 检测
    try:
        with open(file_path, "rb") as f:
            raw_data = f.read()
        detected = chardet.detect(raw_data)
        encoding = detected.get('encoding', 'utf-8')
        confidence = detected.get('confidence', 0)
        
        if confidence > 0.7:
            logger.info(f"📝 chardet 检测到编码: {encoding} (置信度: {confidence:.2f})")
            return raw_data.decode(encoding)
    except Exception as e:
        logger.warning(f"⚠️ chardet 检测失败: {str(e)}")
    
    # 默认使用 UTF-8 (替换错误字符)
    logger.warning(f"⚠️ 尝试使用 UTF-8 (忽略解码错误) 读取 {os.path.basename(file_path)}")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def generate_unique_filename(base_name):
    """生成不重复的输出文件名（避免覆盖）"""
    filename, ext = os.path.splitext(base_name)
    save_path = os.path.join(OUTPUT_FOLDER, f"Article_{filename}{ext}")
    
    if not os.path.exists(save_path):
        return save_path
    
    # 文件已存在，追加序号
    counter = 2
    while True:
        new_path = os.path.join(OUTPUT_FOLDER, f"Article_{filename}_{counter}{ext}")
        if not os.path.exists(new_path):
            return new_path
        counter += 1
        if counter > 1000:  # 防止无限循环
            logger.error("❌ 无法生成唯一文件名")
            return save_path

def call_llm_with_retry(case_content, max_retries=None, initial_delay=None):
    """带指数退避重试的 LLM 调用"""
    max_retries = max_retries if max_retries is not None else LLM_MAX_RETRIES
    initial_delay = initial_delay if initial_delay is not None else LLM_RETRY_DELAY
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"评估报告：{case_content}"}
                ],
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS
            )
            
            article = response.choices[0].message.content
            
            # 检查返回内容是否为空
            if not article or not article.strip():
                logger.warning(f"⚠️ LLM 返回空内容，尝试次数: {attempt + 1}")
                last_exception = ValueError("LLM 返回空内容")
                continue
            
            return article
            
        except AuthenticationError as e:
            logger.error("❌ API认证失败，请检查API密钥")
            raise  # 认证错误不重试
        except RateLimitError as e:
            last_exception = e
            if attempt < max_retries:
                delay = initial_delay * (2 ** attempt)  # 指数退避
                logger.warning(f"⚠️ API限流，{delay:.1f}秒后重试 ({attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                logger.error("❌ API调用超限，已达最大重试次数")
        except APIConnectionError as e:
            last_exception = e
            if attempt < max_retries:
                delay = initial_delay * (2 ** attempt)
                logger.warning(f"⚠️ API连接失败，{delay:.1f}秒后重试 ({attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                logger.error("❌ API连接失败，已达最大重试次数")
        except APIError as e:
            last_exception = e
            if attempt < max_retries:
                delay = initial_delay * (2 ** attempt)
                logger.warning(f"⚠️ API错误: {str(e)}，{delay:.1f}秒后重试 ({attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                logger.error(f"❌ API调用错误，已达最大重试次数: {str(e)}")
        except Exception as e:
            last_exception = e
            logger.error(f"❌ LLM调用失败: {str(e)}")
            break
    
    # 所有重试都失败
    raise last_exception if last_exception else RuntimeError("未知错误")

# ============================================================
# 文件监控
# ============================================================
class FileHandler(FileSystemEventHandler):
    def __init__(self):
        self.processing_files = set()  # 使用完整路径作为键
        self.semaphore = Semaphore(MAX_CONCURRENT_TASKS)
    
    def _get_file_key(self, file_path):
        """生成文件的唯一标识（路径 + inode + mtime）"""
        try:
            stat = os.stat(file_path)
            return f"{file_path}:{stat.st_ino}:{stat.st_mtime}"
        except Exception:
            return file_path
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        if not event.src_path.endswith(".md"):
            return
        
        file_key = self._get_file_key(event.src_path)
        
        if file_key in self.processing_files:
            logger.info(f"⏭️ 跳过重复处理: {os.path.basename(event.src_path)}")
            return
        
        self.processing_files.add(file_key)
        
        try:
            logger.info(f"\n✅ 检测到新文件：{os.path.basename(event.src_path)}")
            
            if not wait_file_stable(event.src_path):
                return
            
            try:
                case_content = read_file_with_encoding_fallback(event.src_path)
                logger.info(f"✅ 文件读取成功，长度: {len(case_content)} 字符")
            except Exception as e:
                logger.error(f"❌ 读取文件失败 {os.path.basename(event.src_path)}: {str(e)}")
                return
            
            if not case_content.strip():
                logger.warning(f"⚠️ 文件内容为空: {os.path.basename(event.src_path)}")
                return
            
            logger.info("🔄 生成文章中...")
            
            try:
                article = call_llm_with_retry(case_content)
                logger.info(f"✅ LLM响应成功，文章长度: {len(article)} 字符")
            except Exception as e:
                logger.error(f"❌ LLM调用失败: {str(e)}")
                return
            
            # 生成唯一文件名（避免覆盖）
            base_name = os.path.basename(event.src_path)
            save_path = generate_unique_filename(base_name)
            
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(article)
                logger.info(f"✅ 文章完成：{save_path}")
            except Exception as e:
                logger.error(f"❌ 保存文章失败: {str(e)}")
                return
            
        finally:
            if file_key in self.processing_files:
                self.processing_files.remove(file_key)

# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Agent启动成功，监控中...")
    logger.info(f"📁 监控目录: {WATCH_FOLDER}")
    logger.info(f"📁 输出目录: {OUTPUT_FOLDER}")
    logger.info(f"⚙️  LLM模型: {LLM_MODEL}")
    logger.info(f"⚙️  并发控制: 最多 {MAX_CONCURRENT_TASKS} 个任务")
    logger.info(f"⚙️  API超时: {LLM_TIMEOUT}秒")
    logger.info(f"⚙️  最大重试: {LLM_MAX_RETRIES}次")
    logger.info("=" * 60)
    
    observer = PollingObserver()
    event_handler = FileHandler()
    
    try:
        observer.schedule(event_handler, WATCH_FOLDER, recursive=False)
        observer.start()
        logger.info("✅ 监控器启动成功")
        
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("⏹️ 收到停止信号，正在退出...")
    except Exception as e:
        logger.error(f"❌ 运行时错误: {str(e)}")
    finally:
        observer.stop()
        observer.join()
        logger.info("✅ Agent已停止")