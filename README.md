# manutencao-api

<br>

## Descrição

Este projeto foi produzido como entrega final do módulo **Desenvolvimento Full Stack Básico** do curso de **Especialização em Desenvovimento Web** da PUC Rio, trata-se de um MVP *(mínimo produto viável)* desenvolvido no formato SPA *(Single page application ou aplicação em página única)* com o objetivo de dar suporte à gestão de manutenções de veículos.

Esta  aplicação é uma API desenvolvida em conjunto com uma página web que consome os dados por ela disponibilizados, no entanto, pode ser consumida por outras aplicações por meio de requisições HTTP, conforme demonstrado neste documento. 

<br>

## Instalação

A API foi desenvolvida na linguagem Python, utilizando o framework Flask. Para executá-la é preciso que o interpretador Python esteja instalado no computador, assim como todas as  dependências *(bibliotecas utilizadas no código da aplicação)*. Para tanto é necessário seguir os passos abaixo:

1. Garantir que o interpretador Python esteja instalado.

    As principais distribuições Linux já vêm com o interpretador Python instalado em uma versão razoavelmente atual, como é o caso do Ubuntu, distribuição Linux utilizada para criação do projeto. No Windows será necessário instalá-lo, caso não tenha feito antes, se for o caso acesse https://www.python.org/downloads/windows/ e siga as instruções apresentadas.

2. Fazer o download da aplicação em https://github.com/erbraga/manutencao-api/archive/refs/heads/main.zip e extraia o diretório compactado no HD.

3. Abrir o terminal e executar os comandos abaixo para criar e ativar o ambiente virtual e instalar as dependências.
    
    No Ubuntu:
    ```
    cd ./ manutencao-api-main
    python3 -m venv .venv
    source ./.bin/activate
    pip install -r requirements.txt
    ```
    
    No Windows:
    ```
    cd manutencao-api-main
    py -m venv .venv
    .venv\Scripts\activate.bat
    pip install -r requirements.txt
    ```

<br>

## Como executar
Após a criação e ativação do ambiente virtual a aplicação pode ser executada por meio do comando ``` flask run  ``` no terminal. 

<br>

## Como executar com Docker

Alternativa ao passo a passo acima: com o [Docker](https://docs.docker.com/engine/install/) instalado, não é necessário criar ambiente virtual nem instalar dependências manualmente.

1. Na raiz do projeto, construir a imagem:
    ```
    docker build -t manutencao-api .
    ```

2. Rodar o container, mapeando a porta 5000 e montando um volume para persistir o banco de dados SQLite entre execuções:
    ```
    docker run -d --name manutencao-api -p 5000:5000 -v "$(pwd)/instance:/app/instance" manutencao-api
    ```

    No Windows (PowerShell), substituir `$(pwd)` por `${PWD}`.

3. A API estará disponível em `http://127.0.0.1:5000`, com o Swagger em `http://127.0.0.1:5000/apidocs/`, da mesma forma que na execução local.

4. Para parar o container:
    ```
    docker stop manutencao-api
    ```

**Atenção:** se o container for removido (`docker rm`) sem o volume `-v` montado como acima, os dados gravados no SQLite são perdidos junto com o container.

<br>

## Como utilizar

A APi pode ser consumida por meio de requisições HTML para as rotas definidas.
Como a aplicação foi desenvolvida para fins acadêmicos, está hospedada em servidor local, por isso o domínio é *127.0.0.1:5000* e as rotas são:

***/apidocs/***<br>
Rota criada pelo **Swagger**  que mostra uma página gerada automaticamente pela ferramenta para exibir a documentação e permite testar todas as rotas da API. 

<br>

***/recuperar***

|Método|GET|
|-|-|
|Funcionalidade|Retorna em um arquivo **JSON** todos os registros das 2 tabelas definidas no Banco de dados.|
|Retorno|Arquivo **JSON** com todos os registros das 2 tabelas definidas no Banco de dados.

<br>

***/alterar-item/{id}***
|Método|PUT|
|-|-|
|Parâmetro|id => chave primária da tabela itens.|
|Funcionalidade|Altera um registro da tabela itens cuja chave primária seja igual a *id*. Os valores são enviados no corpo da requisição.|
|Retorno|200 - Registro atualizado com sucesso!<br>404 - Registro não encontrado|

<br>

***/alterar-veiculo/{id}***
|Método|PUT|
|-|-|
|Parâmetro|id => chave primária da tabela veiculos.|
|Funcionalidade|Altera um registro da tabela veiculos cuja chave primária seja igual a *id*. Os valores são enviados no corpo da requisição.|
|Retorno|200 - Registro atualizado com sucesso!<br>404 - Registro não encontrado|

<br>

***/deletar-item​/{id}***
|Método: |DELETE|
|-|-|
|Parâmetro| id => chave primária da tabela itens.|
|Funcionalidade|Exclui um registro da tabela itens cuja chave primária seja igual a *id*.|
|Retorno|200 - Registro atualizado com sucesso!<br>404 - Registro não encontrado|

<br>

***/deletar-veiculo/{id}***
|Método: |DELETE|
|-|-|
|Parâmetro| id => chave primária da tabela veiculos.|
|Funcionalidade|Exclui um registro da tabela itens cuja chave primária seja igual a *id*.|
|Retorno|200 - Registro atualizado com sucesso!<br>404 - Registro não encontrado<br>500 - Registro associado a uma chave estrangeira|

<br>

***/salvar-item/***
|Método|PUT|
|-|-|
|Parâmetro|id => chave primária da tabela itens.|
|Funcionalidade|Salva um novo registro na tabela itens. Os valores são enviados no corpo da requisição.|
|Retorno|200 - Registro atualizado com sucesso!<br>404 - Registro não encontrado|

<br>

***/salvar-veiculo/***
|Método|PUT|
|-|-|
|Parâmetro|id => chave primária da tabela veiculos.|
|Funcionalidade|Salva um novo registro na tabela veiculos. Os valores são enviados no corpo da requisição.
|Retorno|200 - Registro atualizado com sucesso!<br>404 - Registro não encontrado|

<br>

## Persistência dos dados
Foi criado em banco de dados por meio do SGBD *(Sistema Gerenciador de Banco de Dados)* SQLITE3 com duas tabelas para persistir os dados do aplicativo:

<br>

**Veiculos:**
|coluna|descricao|formato
|-|-|-|
|id|chave primária|integer|
descricao|marca, modelo e versão do veículo|string(50)|

<br>

**Itens:**
|coluna|descricao|formato
|-|-|-|
|id|chave primária|integer|
|descricao|Descrição do item de manutenção|string(100)|
|intervalo_km|Intervalo de troca em quilometros|integer|
|intervalo_prazo|Intervalo de troca em meses|integer|
|ultima_troca_km|quilometragem da última troca|integer|
|ultima_troca_data|data da última troca|integer|
|veiculo| chave estrangeira para associar os ítens a um veículo|integer|

<br>

## Tecnologias utilizadas
- **HTTP:** Protocolo de transmissão de dados utilizada para troca de dados entre o cliente e o servidor em uma aplicação web.
- **Python:** Linguagem de programação interpretada que suporta mais de um paradigma de programação e pode ser utilizada para várias aplicações.
- **Flask:** Biblioteca que possibilita utilizar Python para programar aplicações para web.
- **SQLITE3:** Servidor de banco de dados que roda no computador local, muito utilizado para MVPs e aplicações simples. 
- **Github:** Ferramenta de versionamento, que permite criar diversas versões do código durante o desenvolvimento da aplicação, além do seu compartilhamento.
- **Visual Studio Code (VSCode):** Ambiente de desenvolvimento integrado (IDE) que permite editar todo o código do projeto escrito em mais de uma linguagem em um mesmo ambiente, além de banco de dados e outras ferramentas como **Github**.
