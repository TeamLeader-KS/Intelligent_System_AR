package com.example.intelligent_system_ar.data.remote

object ServerConfig {
    /**
     * true — справочники (цеха/должности/сотрудники) берутся из встроенной заглушки.
     * Вход по логину и паролю (AuthApi) всегда идёт на реальный сервер.
     */
    const val USE_MOCK = true

    /** Адрес сервера. Обязательно со слэшем в конце (требование Retrofit). Нужен только интернет. */
    const val BASE_URL = "https://pet.oppennec.ru/industrial-vision/api/v1/"
}
