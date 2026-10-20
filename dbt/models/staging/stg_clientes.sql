-- Registration cleanup: normalized e-mail, phone with digits only and country code,
-- and identification of duplicate accounts of the same person (same CPF).
with base as (
    select
        cliente_id,
        tipo_cliente,
        tipo_pessoa,
        trim(nome)                                       as nome,
        lower(trim(email))                               as email,
        nullif(regexp_replace(telefone, '[^0-9]', ''), '') as telefone_digitos,
        cpf,
        cnpj,
        data_nascimento,
        genero,
        cadastrado_em,
        origem_cadastro,
        aceita_email_marketing,
        aceita_whatsapp,
        origem_cadastro = 'importacao_legado' as cliente_legado
    from {{ source('raw', 'clientes') }}
    where email not like 'teste.%@tecelatecidos.example'
)
select
    b.*,
    case
        when telefone_digitos is null then null
        when length(telefone_digitos) = 13 and telefone_digitos like '55%' then concat('+', telefone_digitos)
        else concat('+55', telefone_digitos)
    end as telefone_e164,
    -- "canonical" customer: the oldest account with the same CPF
    case when cpf is null then cliente_id
         else min(cliente_id) over (partition by cpf) end as cliente_id_unificado
from base b
