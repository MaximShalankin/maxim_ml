# Некоторые способы оценки качества данных

*В telegram есть еще много чего интересного https://t.me/+HdRZec7VJEVlNmVi*


## Population stability Index
Как рассчитывается PSI? Разберем шаг за шагом

### шаг 1
Сперва нам нужно получить два распределения данных, сравним их визуально друг с другом


![alt text](/theory_and_practice/data_quality/pictures/psi_1.png)


### шаг 2
Разбиваем данные на n бинов, в нашем примере таких бинов 4 штуки. 


![alt text](/theory_and_practice/data_quality/pictures/psi_2.png)

### шаг 3
Считаем количество элементов распределения А и Б в каждом бине.



![alt text](/theory_and_practice/data_quality/pictures/psi_3.png)

### шаг 4
Вычитаем попарно для каждого бина полученные значения количества элементов. Разницу нужно сделать относительной.



![alt text](/theory_and_practice/data_quality/pictures/psi_4.png)

### шаг 5
Делим попарно для каждого бина полученные значения количества элементов.


![alt text](/theory_and_practice/data_quality/pictures/psi_5.png)


Теперь мы можем воспользоваться формулой для расчета PSI: 

PSI = Σ (распределение_а% – распределение_б%) * ln(распределение_а% / распределение_б%)

## Критерий Колмогорова-Смирнова

Как рассчитывается статистика из критерия Колмогорова-Смирнова? Разберем шаг за шагом


### шаг 1
Сперва нам нужно получить два распределения данных, сравним их визуально друг с другом
![alt text](/theory_and_practice/data_quality/pictures/ks_1.png)

### шаг 2
Нужно отсортировать значения в каждом распределении. После чего снова посмотрим на то, как выглядят наши данные. 
![alt text](/theory_and_practice/data_quality/pictures/ks_2.png)


### шаг 3
Нам нужно определить проверяемую гипотезу. Давайте рассмотрим два случая: когда одно распределение может быть "меньше" другого и когда одно распределение может быть "больше" другого.

Для случая less мы предполагаем, что распределение А всегда больше или равно распределению Б.
Для случая greater мы ищем хотя бы одно значение, для которого распределение А меньше, чем Б.
Основная идея заключается в том, чтобы привести одно распределение к другому и найти точки, где различия между ними максимальны (greater) или минимальны (less).

В контексте критерия Колмогорова-Смирнова, максимальные различия между эмпирическими функциями распределения называются статистикой критерия Колмогорова-Смирнова.


![alt text](/theory_and_practice/data_quality/pictures/ks_3.png)


## Adversarial Validation Score

### шаг 1
Нам нужно разметить данные бинарной переменной, где у каждого из распределений будет свое значение метки. Эта метка станет целевой переменной для нашего artificial classifier. Его задача - научиться определять, к какому из двух распределений относится семпл данных. Качество предсказаний будем замерять метрикой бинарной классификации - roc auc score.

![alt text](/theory_and_practice/data_quality/pictures/adv_1.png)

### шаг 2
Распределения могут быть схожи, тогда значение метрики roc auc будет <= 0.55, или наоборот, сильно отличаться. Тогда значение метрики будет >=0.85 (верхняя граница условная и может меняться в зависимости от вашей задачи)

![alt text](/theory_and_practice/data_quality/pictures/adv_2.png)
