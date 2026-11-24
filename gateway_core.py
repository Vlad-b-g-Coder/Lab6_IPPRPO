import json
import urllib.request
import urllib.error


class GatewayError(Exception):
    def __init__(self, message, status):
        Exception.__init__(self, message)
        self.status = status


class CountryResolver:
    def __init__(self, countries):
        if len(countries) == 0:
            raise ValueError("список стран пуст")
        self.index = {}
        for country in countries:
            country_id = country[0]
            country_name = country[1]
            self.index[country_name.lower()] = country_id

    def resolve(self, value):
        text = str(value).strip()
        if text.isdigit():
            return int(text)
        name = text.lower()
        if name not in self.index:
            raise GatewayError("неизвестная страна: " + text, 400)
        return self.index[name]

    def resolve_many(self, text):
        result = []
        for part in text.split(","):
            if part.strip() != "":
                result.append(self.resolve(part))
        return result


class TourFilter:
    def __init__(self, stars_min=None, stars_max=None, price_min=None, price_max=None, limit=None):
        if stars_min is not None and stars_max is not None:
            if stars_min > stars_max:
                raise ValueError("stars_min больше stars_max")
        if limit is not None and limit <= 0:
            raise ValueError("limit должен быть положительным")
        self.stars_min = stars_min
        self.stars_max = stars_max
        self.price_min = price_min
        self.price_max = price_max
        self.limit = limit

    def is_suitable(self, tour):
        stars = tour["stars"]
        if stars is None:
            stars = 0
        price = tour["price"]
        if self.stars_min is not None and stars < self.stars_min:
            return False
        if self.stars_max is not None and stars > self.stars_max:
            return False
        if self.price_min is not None and price < self.price_min:
            return False
        if self.price_max is not None and price > self.price_max:
            return False
        return True

    def apply(self, tours):
        suitable = []
        for tour in tours:
            if self.is_suitable(tour):
                suitable.append(tour)
        suitable.sort(key=lambda tour: tour["price"])
        if self.limit is not None:
            return suitable[:self.limit]
        return suitable


class RemoteForwarder:
    DEFAULT_PORT = 1130

    def __init__(self, timeout=10, token=None):
        self.timeout = timeout
        self.token = token

    def base_url(self, remote):
        remote = remote.strip()
        if remote == "":
            raise GatewayError("адрес удалённой машины пуст", 400)
        if remote.startswith("http://") or remote.startswith("https://"):
            return remote.rstrip("/")
        if ":" in remote:
            return "http://" + remote
        return "http://" + remote + ":" + str(self.DEFAULT_PORT)

    def forward(self, remote, operation, params):
        headers = {"Content-Type": "application/json"}
        if self.token is not None:
            headers["X-Token"] = self.token
        url = self.base_url(remote) + "/" + operation
        data = json.dumps(params).encode()
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
            body = response.read().decode()
        except urllib.error.URLError as error:
            raise GatewayError("удалённая машина недоступна: " + str(error.reason), 502)
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise GatewayError("ответ удалённой машины не JSON", 502)
